"""Plan, apply and verify Minecraft mod migrations."""

import argparse
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .io import atomic_write, inside, json_bytes, read_json, safe_path
from .mappings import lookup
from .planning import make_plan, resolve_target, target_profiles
from .reporting import (
    build_report,
    inventory_markdown,
    matrix_markdown,
    plan_markdown,
    report_markdown,
)
from .rules import load_rules
from .scan import scan
from .workspace import (
    apply_pending,
    create_workspace,
    file_digest,
    open_workspace,
    progress,
    record_operation,
    save_state,
    workspace_fingerprint,
)


def _version() -> str:
    try:
        return version("modstride")
    except PackageNotFoundError:
        return "development checkout"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="modstride", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {_version()}")
    parser.add_argument(
        "--rules-dir", type=Path, help="Additional reviewed rule catalogue"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    inventory = commands.add_parser(
        "scan", help="Statically inventory a mod source directory or JAR"
    )
    inventory.add_argument("source", type=Path)
    inventory.add_argument("--format", choices=["json", "markdown"], default="markdown")

    plan = commands.add_parser(
        "plan", help="Assess a target and write JSON and Markdown plans"
    )
    plan.add_argument("source", type=Path)
    plan.add_argument("--to-version", help="Target Minecraft or engine version")
    plan.add_argument("--to-loader", help="fabric, forge, neoforge or quilt")
    plan.add_argument("--to-engine", default="minecraft", help="minecraft or horizon")
    plan.add_argument("--to-mappings", help="Target mappings, e.g. mojang or yarn")
    plan.add_argument(
        "--output-dir", type=Path, required=True, help="Directory for generated plans"
    )

    apply = commands.add_parser(
        "apply", help="Copy source to a new workspace and apply reviewed rules"
    )
    apply.add_argument("--plan", type=Path, required=True)
    apply.add_argument("--workspace", type=Path, required=True)
    apply.add_argument(
        "--dry-run",
        action="store_true",
        help="Check plan and copy eligibility without writing files",
    )

    verify = commands.add_parser(
        "verify", help="Run static checks and optionally a reviewed Gradle build"
    )
    verify.add_argument("--workspace", type=Path, required=True)
    verify.add_argument(
        "--run-gradle",
        action="store_true",
        help="Authorize execution of reviewed project build code",
    )
    verify.add_argument(
        "--gradle", type=Path, help="Absolute path to a trusted Gradle executable"
    )
    verify.add_argument(
        "--evidence",
        type=Path,
        help="JSON document recording external runtime and gameplay checks",
    )
    verify.add_argument(
        "--timeout", type=int, default=300, help="Gradle timeout in seconds"
    )

    report = commands.add_parser(
        "report", help="Write JSON and Markdown migration reports"
    )
    report.add_argument("--workspace", type=Path, required=True)
    report.add_argument(
        "--output-dir",
        type=Path,
        help="Report directory (default: workspace/.modstride)",
    )

    resume = commands.add_parser(
        "resume", help="Show migration progress or replay pending rules"
    )
    resume.add_argument("--workspace", type=Path, required=True)
    actions = resume.add_mutually_exclusive_group()
    actions.add_argument(
        "--apply", action="store_true", help="Replay pending deterministic rules"
    )
    actions.add_argument(
        "--record",
        nargs=2,
        metavar=("OPERATION", "EVIDENCE"),
        help="Record completed manual review using a workspace-relative evidence file",
    )

    catalogue = commands.add_parser(
        "rules", help="List, inspect and validate rule catalogues"
    )
    operations = catalogue.add_subparsers(dest="action", required=True)
    operations.add_parser("list", help="List rules and review status")
    show = operations.add_parser("show", help="Print a rule as JSON")
    show.add_argument("id")
    operations.add_parser("validate", help="Validate schemas and detect conflicts")

    mappings = commands.add_parser("mappings", help="Inspect user-supplied mappings")
    mapping_commands = mappings.add_subparsers(dest="action", required=True)
    symbol = mapping_commands.add_parser(
        "lookup", help="Look up an exact symbol in a Tiny v2 table"
    )
    symbol.add_argument("table", type=Path)
    symbol.add_argument("--namespace", required=True)
    symbol.add_argument("--owner", required=True, help="Slash-separated JVM class name")
    symbol.add_argument("--member", help="Exact field or method name")
    symbol.add_argument(
        "--descriptor", help="JVM descriptor in the table's first namespace"
    )
    return parser


def _print_json(data) -> None:
    print(json_bytes(data).decode("utf-8"), end="")


def _output(
    directory: Path, documents: dict[str, bytes], *, replace: bool = False
) -> None:
    directory = safe_path(directory, missing=True)
    directory.mkdir(parents=True, exist_ok=True)
    paths = [
        (inside(directory, name, missing=True), payload)
        for name, payload in documents.items()
    ]
    if not replace and any(path.exists() for path, _ in paths):
        raise ValueError(
            f"Generated documents already exist in {directory}; choose another output directory"
        )
    for path, payload in paths:
        atomic_write(path, payload)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except (OSError, ValueError, RecursionError) as error:
        print(f"modstride: {error}", file=sys.stderr)
        return 2


def _run(args: argparse.Namespace) -> int:
    command = args.command
    if command == "scan":
        inventory = scan(args.source)
        if args.format == "json":
            _print_json(inventory)
        else:
            print(inventory_markdown(inventory), end="")
    elif command == "plan":
        target = resolve_target(
            args.to_version, args.to_loader, args.to_engine, args.to_mappings
        )
        source = safe_path(args.source)
        destination = safe_path(args.output_dir, missing=True)
        if source.is_dir() and destination.is_relative_to(source):
            raise ValueError("Write the plan outside the original source tree")
        plan = make_plan(source, target, load_rules(args.rules_dir))
        _output(
            destination,
            {
                "migration-plan.json": json_bytes(plan),
                "MIGRATION_PLAN.md": plan_markdown(plan).encode("utf-8"),
                "COMPATIBILITY_MATRIX.md": matrix_markdown(plan).encode("utf-8"),
            },
        )
        print(destination / "migration-plan.json")
    elif command == "rules":
        rules = load_rules(args.rules_dir)
        if args.action == "list":
            _print_json(
                [
                    {
                        "id": rule.id,
                        "title": rule.data["title"],
                        "status": rule.data["status"],
                    }
                    for rule in rules.values()
                ]
            )
        elif args.action == "show":
            if args.id not in rules:
                raise ValueError(f"Unknown rule: {args.id}")
            _print_json(rules[args.id].data)
        else:
            target_profiles()
            print(f"Validated {len(rules)} rules and target profiles")
    elif command == "apply":
        state = create_workspace(
            read_json(safe_path(args.plan)),
            args.workspace,
            load_rules(args.rules_dir),
            dry_run=args.dry_run,
        )
        _print_json(
            state
            if args.dry_run
            else {
                "workspace": str(args.workspace.absolute()),
                "completed": state["completed"],
            }
        )
    elif command == "mappings":
        _print_json(
            lookup(args.table, args.namespace, args.owner, args.member, args.descriptor)
        )
    else:
        with open_workspace(args.workspace) as (root, state):
            return _run_workspace(args, root, state)
    return 0


def _run_workspace(args: argparse.Namespace, root: Path, state: dict) -> int:
    if args.command == "resume":
        if args.apply:
            apply_pending(root, state, load_rules(args.rules_dir))
        elif args.record:
            record_operation(root, state, *args.record)
        _print_json(progress(root, state))
    elif args.command == "verify":
        from .verification import verify

        if not 1 <= args.timeout <= 3600:
            raise ValueError("Verification timeout must be between 1 and 3600 seconds")
        if args.gradle and not args.run_gradle:
            raise ValueError("--gradle requires --run-gradle")
        if args.gradle and not args.gradle.is_absolute():
            raise ValueError("--gradle requires an absolute launcher path")
        before = workspace_fingerprint(root)
        result = verify(
            root,
            state,
            run_gradle=args.run_gradle,
            gradle=args.gradle,
            evidence=args.evidence,
            timeout=args.timeout,
        )
        result["workspace_sha256"] = before
        verification_args = ["modstride", "verify", "--workspace", str(root)]
        if args.run_gradle:
            verification_args += ["--run-gradle", "--timeout", str(args.timeout)]
        if args.gradle:
            verification_args += ["--gradle", str(args.gradle)]
        if args.evidence:
            verification_args += ["--evidence", str(args.evidence.absolute())]
        result["command"] = verification_args
        logs = {
            item
            for stage in result["stages"]
            for item in stage["evidence"]
            if item.startswith(".modstride/gradle-") and item.endswith(".log")
        }
        result["evidence_hashes"] = {
            name: file_digest(inside(root, name)) for name in sorted(logs)
        }
        result["evidence_hashes"].update(
            {item["path"]: item["sha256"] for item in result["artifacts"]}
        )
        state["generated_files"] = sorted(set(state["generated_files"]) | logs)
        state["verification"] = result
        save_state(root, state)
        _print_json(result)
        if any(stage["status"] in {"failed", "blocked"} for stage in result["stages"]):
            return 1
    elif args.command == "report":
        destination = safe_path(args.output_dir or root / ".modstride", missing=True)
        source = Path(state["plan"]["source"]["source"])
        if destination.is_relative_to(source):
            raise ValueError("Write the report outside the original source tree")
        if destination.is_relative_to(root) and destination != root / ".modstride":
            raise ValueError(
                "Use the managed report directory or a directory outside the workspace"
            )
        if destination == root / ".modstride":
            state["generated_files"] = sorted(
                set(state["generated_files"])
                | {".modstride/migration-report.json", ".modstride/MIGRATION_REPORT.md"}
            )
        report = build_report(root, state)
        _output(
            destination,
            {
                "migration-report.json": json_bytes(report),
                "MIGRATION_REPORT.md": report_markdown(report).encode("utf-8"),
            },
            replace=args.output_dir is None,
        )
        if destination == root / ".modstride":
            save_state(root, state)
        print(destination / "MIGRATION_REPORT.md")
    return 0
