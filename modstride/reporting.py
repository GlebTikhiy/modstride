"""Markdown views of JSON plans, inventories and workspace evidence."""

import shlex
from pathlib import Path

from .workspace import progress, snapshot


def _cell(value) -> str:
    return (
        str(value if value is not None else "unknown")
        .replace("|", r"\|")
        .replace("\n", " ")
        .replace("\r", " ")
    )


def _table(headers: list[str], rows) -> str:
    return "\n".join(
        "| " + " | ".join(map(_cell, row)) + " |"
        for row in [headers, ["---"] * len(headers), *rows]
    )


def _facts(inventory: dict) -> str:
    return _table(
        ["Fact", "Value", "Confidence", "Evidence"],
        [
            (name, entry["value"], entry["confidence"], ", ".join(entry["evidence"]))
            for name, entry in inventory["environment"].items()
        ],
    )


def inventory_markdown(inventory: dict) -> str:
    dependencies = [
        (
            item.get("id"),
            item.get("requirement"),
            item.get("kind"),
            item.get("evidence"),
        )
        for item in inventory["dependencies"]
    ]
    return "\n".join(
        [
            "# Mod inventory",
            "",
            str(inventory["source"]),
            "",
            _facts(inventory),
            "",
            "## Mod IDs",
            "",
            ", ".join(inventory["mod_ids"]) or "Unknown",
            "",
            "## Dependencies",
            "",
            _table(["ID", "Requirement", "Kind", "Evidence"], dependencies),
            "",
            "## Source and resources",
            "",
            *(
                f"- {name}"
                for name in inventory["source_directories"]
                + inventory["resource_directories"]
            ),
            "",
            "## Subsystem signals",
            "",
            _table(
                ["Subsystem", "Signals"],
                [
                    (name, ", ".join(signals))
                    for name, signals in inventory["subsystems"].items()
                ],
            ),
            "",
            "## Warnings",
            "",
            *(f"- {warning}" for warning in inventory["warnings"]),
            "",
        ]
    )


def matrix_markdown(plan: dict) -> str:
    rows = [
        (
            entry["subsystem"],
            entry["assessment"],
            entry["risk"],
            ", ".join(entry["signals"]),
            entry["guidance"],
        )
        for entry in plan["compatibility"]
    ]
    return (
        "# Compatibility matrix\n\n"
        + _table(["Subsystem", "Assessment", "Risk", "Signals", "Review"], rows)
        + "\n"
    )


def plan_markdown(plan: dict) -> str:
    target = plan["target"]
    rows = [
        (
            entry["id"],
            entry["kind"],
            entry["status"],
            ", ".join(entry["dependencies"]),
            " ".join(entry["verification"]),
        )
        for entry in plan["operations"]
    ]
    return "\n".join(
        [
            "# Migration plan",
            "",
            _facts(plan["source"]),
            "",
            "## Target",
            "",
            _table(["Field", "Value"], list(target.items())),
            "",
            "## Strategy",
            "",
            f"**{plan['strategy']}**. {plan['rationale']}",
            "",
            "## Operations",
            "",
            _table(["ID", "Kind", "Status", "Depends on", "Verification"], rows),
            "",
            "## Deferred rules",
            "",
            *(
                f"- {rule['rule']} — {rule['reason']}"
                for rule in plan["deferred_rules"]
            ),
            "",
            "## Limitations",
            "",
            *(f"- {item}" for item in plan["limitations"]),
            "",
        ]
    )


def build_report(root: Path, state: dict) -> dict:
    plan = state["plan"]
    status = progress(root, state)
    baseline, current = state["baseline"], snapshot(root)
    changed_files = {
        name: "removed"
        if name not in current
        else "added"
        if name not in baseline
        else "modified"
        for name in sorted(baseline.keys() | current.keys())
        if baseline.get(name) != current.get(name)
    }
    verification = status["verification"]
    gameplay = (
        next(
            (
                stage["status"]
                for stage in verification["stages"]
                if stage["id"] == "gameplay"
            ),
            "not available",
        )
        if verification and not status["verification_stale"]
        else "not available"
    )
    if (
        any(item["kind"] == "manual" for item in status["pending"])
        and gameplay == "passed"
    ):
        gameplay = "blocked"
    failures = (
        [
            {"stage": stage["id"], "detail": stage["detail"]}
            for stage in (verification or {}).get("stages", [])
            if stage["status"] == "failed"
        ]
        if not status["verification_stale"]
        else []
    )
    return {
        "schema_version": 1,
        "source": plan["source"],
        "target": plan["target"],
        "strategy": plan["strategy"],
        "progress": status,
        "changed_files": changed_files,
        "subsystems_under_review": [
            row["subsystem"] for row in plan["compatibility"] if row["signals"]
        ],
        "gameplay_parity": gameplay,
        "observed_failures": failures,
        "known_regressions": [
            failure for failure in failures if failure["stage"] == "gameplay"
        ],
        "limitations": plan["limitations"],
        "deferred_rules": plan["deferred_rules"],
        "unverified_assumptions": [
            item["title"] for item in status["pending"] if item["kind"] == "manual"
        ],
        "reproduction": [
            ["modstride", "resume", "--workspace", str(root)],
            (verification or {}).get(
                "command", ["modstride", "verify", "--workspace", str(root)]
            ),
            ["modstride", "report", "--workspace", str(root)],
        ],
    }


def report_markdown(report: dict) -> str:
    status = report["progress"]
    verification = status["verification"]
    notes = "No verification run recorded."
    rows = []
    if verification:
        notes = (
            "Recorded verification."
            if not status["verification_stale"]
            else (
                "Workspace inputs changed after verification. Run verification again for current evidence."
            )
        )
        rows = [
            (
                stage["id"],
                stage["status"],
                stage.get("provenance", "CLI"),
                stage["detail"],
                ", ".join(stage.get("evidence", [])),
            )
            for stage in verification["stages"]
        ]
    return "\n".join(
        [
            "# Migration report",
            "",
            str(status["workspace"]),
            "",
            "## Original environment",
            "",
            _facts(report["source"]),
            "",
            "## Target environment",
            "",
            _table(["Field", "Value"], list(report["target"].items())),
            "",
            "## Applied rules and review evidence",
            "",
            _table(
                ["Operation", "Kind", "Path", "SHA-256"],
                [
                    (name, item["kind"], item["path"], item["sha256"])
                    for name, item in status["completed"].items()
                ],
            ),
            "",
            "## Changed workspace files",
            "",
            _table(["Path", "Change"], report["changed_files"].items()),
            "",
            "Subsystems flagged for review",
            "",
            *(f"- {subsystem}" for subsystem in report["subsystems_under_review"]),
            "",
            "## Verification",
            "",
            notes,
            "",
            _table(["Stage", "Status", "Provenance", "Details", "Evidence"], rows),
            "",
            "Build artifacts",
            "",
            *(
                f"- `{artifact['path']}` · SHA-256 `{artifact['sha256']}`"
                for artifact in (verification or {}).get("artifacts", [])
            ),
            "",
            f"Gameplay parity status: **{report['gameplay_parity']}**.",
            "",
            "## Remaining work and regressions",
            "",
            *(f"- {entry['id']}: {entry['title']}" for entry in status["pending"]),
            *(
                f"- Evidence changed or missing: {name}"
                for name in status["changed_or_missing_evidence"]
            ),
            *(
                f"- Failed {failure['stage']}: {failure['detail']}"
                for failure in report["observed_failures"]
            ),
            *(
                f"- Gameplay regression evidence: {failure['detail']}"
                for failure in report["known_regressions"]
            ),
            "",
            "## Compatibility and unverified assumptions",
            "",
            *(
                f"- {item}"
                for item in report["limitations"] + report["unverified_assumptions"]
            ),
            *(
                f"- Deferred rule {item['rule']}: {item['reason']}"
                for item in report["deferred_rules"]
            ),
            "",
            "## Reproduce",
            "",
            "Run the CLI with these arguments (POSIX shell quoting shown).",
            "",
            "~~~sh",
            *(shlex.join(command) for command in report["reproduction"]),
            "~~~",
            "",
        ]
    )
