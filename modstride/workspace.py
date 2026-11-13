"""Isolated source copies, crash recovery and evidence-backed progress."""

import hashlib
import os
import shutil
import stat
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .io import atomic_write, digest, inside, is_link, json_bytes, read_json, safe_path
from .planning import environment, validate_plan
from .rules import Rule
from .scan import scan

STATE_DIR = ".modstride"
STATE_FILE = ".modstride/state.json"
EXCLUDED = {
    ".git",
    ".gradle",
    ".idea",
    ".vscode",
    ".modstride",
    ".venv",
    "build",
    "out",
    "target",
    "run",
    "runs",
    "saves",
    "world",
    "world_nether",
    "world_the_end",
}


def project_files(root: Path) -> Iterator[tuple[Path, str]]:
    def visit(directory: Path) -> Iterator[tuple[Path, str]]:
        names: set[str] = set()
        under_source = "src" in {
            part.casefold() for part in directory.relative_to(root).parts
        }
        for item in sorted(directory.iterdir(), key=lambda entry: entry.name):
            normalized = item.name.casefold()
            if normalized in EXCLUDED and (
                normalized.startswith(".") or not under_source
            ):
                continue
            if normalized in names:
                raise ValueError(
                    f"Case-insensitive path collision under {directory}: {item.name}"
                )
            names.add(normalized)
            info = item.lstat()
            relative = item.relative_to(root).as_posix()
            inside(root, relative)
            if is_link(info):
                raise ValueError(f"Source contains a symlink or reparse point: {item}")
            if stat.S_ISDIR(info.st_mode):
                # Named world directories can contain live saves anywhere in a source tree.
                if not (item / "level.dat").exists():
                    yield from visit(item)
            elif stat.S_ISREG(info.st_mode):
                yield item, relative
            else:
                raise ValueError(f"Source contains a special file: {item}")

    yield from visit(safe_path(root))


def file_digest(path: Path) -> str:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f"Expected a regular file: {path}")
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def snapshot(root: Path) -> dict[str, str]:
    return {relative: file_digest(path) for path, relative in project_files(root)}


def workspace_fingerprint(root: Path) -> str:
    hasher = hashlib.sha256()
    for relative, content_hash in snapshot(root).items():
        hasher.update(
            relative.encode("utf-8") + b"\0" + content_hash.encode("ascii") + b"\n"
        )
    return hasher.hexdigest()


def _destination(plan: dict, destination: Path) -> tuple[Path, Path]:
    source = safe_path(Path(plan["source"]["source"]))
    destination = safe_path(destination, missing=True)
    if plan["source"]["kind"] != "directory" or not source.is_dir():
        raise ValueError(
            "JAR plans are assessment-only. Apply requires a source directory."
        )
    if source.is_relative_to(destination) or destination.is_relative_to(source):
        raise ValueError("The workspace and source must be disjoint directories")
    if destination.exists():
        raise ValueError(
            "Workspace already exists. Use resume --apply for a managed workspace."
        )
    return source, destination


def _rule_for(operation: dict, plan: dict, rules: dict[str, Rule]) -> Rule:
    rule = rules.get(operation["id"])
    if (
        rule is None
        or rule.data["status"] != "trusted"
        or not rule.matches(environment(plan["source"], confirmed=True), plan["target"])
        or rule.fingerprint != operation["rule_fingerprint"]
        or rule.data["path"] != operation.get("path")
    ):
        raise ValueError(f"Rule catalogue or plan changed for {operation['id']}")
    return rule


def _prepared(root: Path, operation: dict, plan: dict, rules: dict[str, Rule]):
    rule = _rule_for(operation, plan, rules)
    path, before, after = rule.prepare(root)
    old, new = digest(before), digest(after)
    if (
        old not in {operation["before"], operation["after"]}
        or new != operation["after"]
    ):
        raise ValueError(
            f"Input changed for {rule.id}. Review the drift before continuing."
        )
    return path, before, after


def _preflight(root: Path, plan: dict, rules: dict[str, Rule]) -> list[dict]:
    if scan(root) != plan["source"]:
        raise ValueError(
            "Source inventory changed since planning. Generate a fresh plan."
        )
    candidates = []
    for operation in plan["operations"]:
        if operation["kind"] == "rule":
            _, before, after = _prepared(root, operation, plan, rules)
            if before == after:
                raise ValueError(f"Source rule already retargeted: {operation['id']}")
            candidates.append({"id": operation["id"], "path": operation["path"]})
    return candidates


def create_workspace(
    plan: dict, destination: Path, rules: dict[str, Rule], *, dry_run: bool
) -> dict:
    plan = validate_plan(plan)
    source, destination = _destination(plan, destination)
    candidates = _preflight(source, plan, rules)
    if dry_run:
        count = sum(1 for _ in project_files(source))
        return {
            "workspace": str(destination),
            "dry_run": True,
            "rules": candidates,
            "copy_files": count,
        }
    destination.parent.mkdir(parents=True, exist_ok=True)
    # A sibling reservation serializes initial publication by cooperating CLI processes.
    reservation = destination.with_name("." + destination.name + ".modstride-create")
    with file_lock(reservation):
        if destination.exists():
            raise ValueError(f"Workspace already exists: {destination}")
        with tempfile.TemporaryDirectory(
            dir=destination.parent, prefix=".modstride-copy-"
        ) as scratch:
            stage = Path(scratch) / "project"
            stage.mkdir()
            baseline = {}
            for path, relative in project_files(source):
                copy = inside(stage, relative, missing=True)
                copy.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, copy)
                baseline[relative] = file_digest(copy)
            # Scan evidence paths are source-relative. Confirm the copy has the planned rule bytes.
            for operation in plan["operations"]:
                if operation["kind"] == "rule":
                    _prepared(stage, operation, plan, rules)
            (stage / STATE_DIR).mkdir()
            state = {
                "schema_version": 1,
                "plan": plan,
                "completed": {},
                "verification": None,
                "baseline": baseline,
                "generated_files": [STATE_FILE],
            }
            save_state(stage, state)
            stage.rename(destination)
    with open_workspace(destination) as (root, state):
        apply_pending(root, state, rules)
        return state


@contextmanager
def file_lock(path: Path):
    path = safe_path(path, missing=True)
    if path.exists() and not path.is_file():
        raise ValueError(f"Expected a regular lock file: {path}")
    with path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise ValueError(f"Another modstride operation holds {path}") from error
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError(f"Another modstride operation holds {path}") from error
            yield


@contextmanager
def open_workspace(workspace: Path):
    root = safe_path(workspace)
    directory = inside(root, STATE_DIR)
    if not directory.is_dir():
        raise ValueError("Expected a managed .modstride directory")
    with file_lock(inside(root, STATE_DIR + "/.lock", missing=True)):
        state = read_json(inside(root, STATE_FILE))
        if (
            not isinstance(state, dict)
            or type(state.get("schema_version")) is not int
            or state["schema_version"] != 1
            or not isinstance(state.get("completed"), dict)
            or not isinstance(state.get("baseline"), dict)
            or not isinstance(state.get("generated_files"), list)
            or "verification" not in state
        ):
            raise ValueError("Unsupported workspace state")
        validate_plan(state.get("plan"))
        yield root, state


def save_state(root: Path, state: dict) -> None:
    atomic_write(inside(root, STATE_FILE, missing=True), json_bytes(state))


def apply_pending(root: Path, state: dict, rules: dict[str, Rule]) -> None:
    plan = state["plan"]
    completed = valid_completions(root, state)
    pending = []
    for operation in plan["operations"]:
        if operation["kind"] != "rule" or operation["id"] in state["completed"]:
            continue
        if not set(operation["dependencies"]) <= completed.keys():
            continue
        pending.append((operation, *_prepared(root, operation, plan, rules)))
        completed[operation["id"]] = None
    for operation, path, before, after in pending:
        if path.read_bytes() != before:
            raise ValueError(f"Concurrent change to {operation['path']}")
        if before != after:
            atomic_write(path, after)
        if file_digest(path) != operation["after"]:
            raise ValueError(f"Postcondition failed for {operation['id']}")
        state["completed"][operation["id"]] = {
            "kind": "rule",
            "path": operation["path"],
            "sha256": operation["after"],
            "action": "applied" if before != after else "recovered",
        }
        state["verification"] = None
        save_state(root, state)


def record_operation(root: Path, state: dict, operation_id: str, evidence: str) -> None:
    operation = next(
        (entry for entry in state["plan"]["operations"] if entry["id"] == operation_id),
        None,
    )
    if operation is None or operation["kind"] != "manual":
        raise ValueError("Only known manual operations accept reviewed evidence")
    if not set(operation["dependencies"]) <= valid_completions(root, state).keys():
        raise ValueError(f"Complete and verify dependencies for {operation_id} first")
    path = inside(root, evidence)
    if not path.is_file() or not path.stat().st_size:
        raise ValueError(
            "Evidence must be a nonempty regular file inside the workspace"
        )
    if evidence.split("/")[0].casefold() in {".git", ".modstride"}:
        raise ValueError("Use an evidence file outside managed state and Git metadata")
    state["completed"][operation_id] = {
        "kind": "manual",
        "path": evidence,
        "sha256": file_digest(path),
        "action": "reviewed-evidence",
    }
    save_state(root, state)


def valid_completions(root: Path, state: dict) -> dict:
    completed = {}
    for operation in state["plan"]["operations"]:
        operation_id = operation["id"]
        record = state["completed"].get(operation_id)
        if not isinstance(record, dict) or record.get("kind") != operation["kind"]:
            continue
        if not set(operation["dependencies"]) <= completed.keys():
            continue
        try:
            if operation["kind"] == "rule" and (
                record["path"] != operation["path"]
                or record["sha256"] != operation["after"]
            ):
                continue
            path = inside(root, record["path"])
            if path.is_file() and file_digest(path) == record["sha256"]:
                completed[operation_id] = record
        except (KeyError, OSError, TypeError, ValueError):
            continue
    return completed


def current_verification(root: Path, state: dict) -> tuple[dict | None, bool]:
    result = state["verification"]
    if result is None:
        return None, False
    if result.get("workspace_sha256") != workspace_fingerprint(root):
        return result, True
    for name, expected in result.get("evidence_hashes", {}).items():
        try:
            if file_digest(inside(root, name)) != expected:
                return result, True
        except (OSError, ValueError):
            return result, True
    return result, False


def progress(root: Path, state: dict) -> dict:
    completed = valid_completions(root, state)
    verification, stale = current_verification(root, state)
    verified = set()
    if verification and not stale:
        required = {
            "target",
            "build",
            "compile",
            "dedicated-server",
            "client",
            "gameplay",
        }
        passed = {
            stage["id"]
            for stage in verification["stages"]
            if stage["status"] == "passed"
        }
        if required <= passed:
            verified = {
                entry["id"]
                for entry in state["plan"]["operations"]
                if entry["kind"] == "verification"
                and set(entry["dependencies"]) <= completed.keys()
            }
    return {
        "workspace": str(root),
        "completed": completed,
        "changed_or_missing_evidence": sorted(
            set(state["completed"]) - completed.keys()
        ),
        "verified_operations": sorted(verified),
        "pending": [
            entry
            for entry in state["plan"]["operations"]
            if entry["id"] not in completed and entry["id"] not in verified
        ],
        "generated_files": state["generated_files"],
        "verification": verification,
        "verification_stale": stale,
    }
