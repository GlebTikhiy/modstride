"""Offline project checks and explicitly authorized Gradle verification."""

import hashlib
import os
import re
import shutil
import stat
import subprocess
import tomllib
import uuid
from pathlib import Path
from typing import Any

from .io import inside, is_link, json_load, read_json, safe_path
from .probes import (
    MARKER,
    TASK_NAME,
    check_readiness,
    gradle_launcher,
    parity,
    run_probe,
)
from .scan import scan
from .workspace import snapshot

TASK = re.compile(r"^> Task (:\S+)(?: (\S+))?$")
MISSING_DEPENDENCY = re.compile(
    r"could not resolve|could not find (?:any matches|[^\n]+:[^\n]+:)|"
    r"plugin \[id: .*\] was not found|failed to (?:setup minecraft|download)|"
    r"could not (?:get|head) resource",
    re.IGNORECASE,
)
MANUAL_STAGES = ("dedicated-server", "client", "gameplay")
MAX_VALIDATION_FILES = 5_000
MAX_RESOURCE_BYTES = 4 * 1024 * 1024


def stage(
    identifier: str, status: str, detail: str, evidence: list[str] | None = None
) -> dict[str, Any]:
    return {
        "id": identifier,
        "status": status,
        "detail": detail,
        "evidence": evidence or [],
    }


def _read_regular(path: Path, limit: int) -> bytes:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f"Expected a regular file: {path}")
    with path.open("rb") as stream:
        content = stream.read(limit + 1)
    if len(content) > limit:
        raise ValueError(f"File exceeds {limit} bytes: {path.name}")
    return content


def _sha256(path: Path) -> str:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f"Expected a regular file: {path}")
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _validate_metadata(path: Path) -> None:
    content = _read_regular(path, MAX_RESOURCE_BYTES)
    if path.suffix == ".toml":
        metadata = tomllib.loads(content.decode("utf-8-sig"))
        mods = metadata.get("mods")
        if (
            not isinstance(mods, list)
            or not mods
            or not all(
                isinstance(mod, dict)
                and isinstance(mod.get("modId"), str)
                and mod["modId"]
                for mod in mods
            )
        ):
            raise ValueError("Expected a nonempty [[mods]] list with modId strings")
        return

    metadata = json_load(content)
    if path.name == "fabric.mod.json":
        if (
            not isinstance(metadata, dict)
            or type(metadata.get("schemaVersion")) is not int
            or metadata["schemaVersion"] != 1
            or not isinstance(metadata.get("id"), str)
            or not re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", metadata["id"])
            or not isinstance(metadata.get("version"), str)
            or not metadata["version"]
        ):
            raise ValueError(
                "Expected Fabric schemaVersion 1, a valid mod id and a version string"
            )
    elif path.name == "quilt.mod.json":
        loader = metadata.get("quilt_loader") if isinstance(metadata, dict) else None
        if not isinstance(loader, dict) or not loader.get("id"):
            raise ValueError("Expected quilt_loader.id")
    elif not isinstance(metadata, (dict, list)):
        raise ValueError("Expected a legacy metadata object or list")


def _check_files(
    workspace: Path, names: list[str], *, metadata: bool
) -> dict[str, Any]:
    identifier = "metadata" if metadata else "resources"
    if not names:
        return stage(
            identifier, "not available", "No files found in supported layouts."
        )
    failures = []
    for name in names[:MAX_VALIDATION_FILES]:
        try:
            path = inside(workspace, name)
            if metadata:
                _validate_metadata(path)
            else:
                json_load(_read_regular(path, MAX_RESOURCE_BYTES))
        except (OSError, ValueError, RecursionError) as exc:
            failures.append(f"{name}: {exc}")
    if failures:
        return stage(
            identifier,
            "failed",
            f"{len(failures)} invalid or unreadable files.",
            failures,
        )
    if len(names) > MAX_VALIDATION_FILES:
        return stage(
            identifier,
            "blocked",
            f"Validation limit reached at {MAX_VALIDATION_FILES} files.",
        )
    description = (
        "metadata syntax and required fields" if metadata else "JSON resource syntax"
    )
    return stage(
        identifier, "passed", f"Checked {description} in {len(names)} files.", names
    )


def _offline_checks(
    workspace: Path, inventory: dict, target: dict
) -> list[dict[str, Any]]:
    structure = inventory["source_directories"] or inventory["resource_directories"]
    layout = stage(
        "structure", "passed", "Conventional project directories found.", structure
    )
    if not structure:
        layout = stage(
            "structure",
            "not available",
            "No conventional source or resource directory found.",
        )

    declarations = []
    mismatches = []
    unknown = []
    for field, scan_key in (
        ("version", "minecraft"),
        ("loader", "loader"),
        ("mappings", "mappings"),
    ):
        expected = target.get(field)
        if not expected or expected == "unknown":
            continue
        detection = inventory["environment"][scan_key]
        actual = detection["value"]
        if detection["confidence"] != "confirmed":
            unknown.append(
                f"{field}: expected {expected}, found {actual or 'unknown'} ({detection['confidence']})"
            )
        elif actual != expected:
            mismatches.append(f"{field}: expected {expected}, found {actual}")
        else:
            declarations.extend(detection["evidence"])

    if target["engine"] != "minecraft":
        match = stage(
            "target",
            "not available",
            "No executable verification adapter for this engine.",
        )
    elif mismatches:
        match = stage(
            "target",
            "failed",
            "Confirmed declarations differ from the target.",
            mismatches,
        )
    elif unknown or not declarations:
        match = stage(
            "target",
            "blocked",
            "The target declarations could not be confirmed.",
            unknown,
        )
    else:
        match = stage(
            "target",
            "passed",
            "Confirmed project declarations match the requested target.",
            declarations,
        )

    metadata = inventory["metadata_files"]
    resources = [
        name
        for name in inventory["resources"]
        if name not in metadata and name.lower().endswith((".json", ".mcmeta"))
    ]
    return [
        layout,
        match,
        _check_files(workspace, metadata, metadata=True),
        _check_files(workspace, resources, metadata=False),
    ]


def _gradle_path(workspace: Path, gradle: Path | None) -> Path | None:
    if gradle is not None:
        launcher = safe_path(gradle, missing=True)
        return launcher if launcher.is_file() else None
    suffix = ".bat" if os.name == "nt" else ""
    wrapper = inside(workspace, f"gradlew{suffix}", missing=True)
    if wrapper.is_file():
        return wrapper
    installed = shutil.which("gradle")
    return Path(installed) if installed else None


def _task_status(
    tasks: list[tuple[str, str]], pattern: str, *, require_execution: bool = False
) -> str:
    outcomes = [
        result
        for name, result in tasks
        if re.fullmatch(pattern, name.rsplit(":", 1)[-1])
    ]
    if "FAILED" in outcomes:
        return "failed"
    successes = {""} if require_execution else {"", "UP-TO-DATE", "FROM-CACHE"}
    if any(result in successes for result in outcomes):
        return "passed"
    return "skipped" if outcomes else "not available"


def _read_build_log(path: Path) -> tuple[list[tuple[str, str]], bool]:
    tasks = []
    dependency_error = False
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            task = TASK.fullmatch(line.strip())
            if task:
                tasks.append((task[1], task[2] or ""))
            dependency_error |= bool(MISSING_DEPENDENCY.search(line))
    return tasks, dependency_error


def _discover_artifacts(workspace: Path) -> dict[str, tuple[str, int]]:
    folder = inside(workspace, "build/libs", missing=True)
    if not folder.is_dir():
        return {}
    return {
        path.relative_to(workspace).as_posix(): (_sha256(path), path.stat().st_mtime_ns)
        for path in sorted(folder.glob("*.jar"))
        if not is_link(path.lstat())
        and path.is_file()
        and not path.stem.endswith(("-sources", "-javadoc", "-dev"))
    }


def _gradle_checks(
    workspace: Path, *, gradle: Path | None, timeout: int
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    executable = _gradle_path(workspace, gradle)
    if executable is None:
        return _build_unavailable("blocked", "Gradle launcher was not found."), []
    command = [
        str(gradle_launcher(executable)),
        "--no-daemon",
        "--console=plain",
        "build",
    ]

    before = _discover_artifacts(workspace)
    log_name = f".modstride/gradle-{uuid.uuid4().hex}.log"
    log = inside(workspace, log_name, missing=True)
    with log.open("xb") as stream:
        try:
            result = subprocess.run(
                command,
                cwd=workspace,
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return _build_unavailable(
                "blocked", f"Gradle exceeded {timeout}s.", [log_name]
            ), []
        except OSError as exc:
            return _build_unavailable(
                "blocked", f"Gradle could not start: {exc}", [log_name]
            ), []

    tasks, dependency_error = _read_build_log(log)
    build_status = "passed" if result.returncode == 0 else "failed"
    compile_status = _task_status(tasks, r"compile(?:Java|Kotlin|Scala|Groovy)")
    tests_status = _task_status(tasks, r"test", require_execution=True)
    if result.returncode and compile_status == "not available":
        compile_status = "blocked"
    if result.returncode and tests_status == "not available":
        tests_status = "blocked"
    if result.returncode and dependency_error:
        dependency_status = "failed"
        dependency_detail = (
            "Gradle reported a dependency, plugin, or Minecraft setup resolution error."
        )
    elif compile_status == "passed":
        dependency_status = "passed"
        dependency_detail = (
            "Gradle satisfied the dependency classpath for the observed compilation."
        )
    else:
        dependency_status = "not available"
        dependency_detail = "No task evidence to establish dependency resolution."
    after = _discover_artifacts(workspace) if result.returncode == 0 else {}
    artifacts = [
        {"path": path, "sha256": info[0]}
        for path, info in after.items()
        if before.get(path) != info
    ]
    evidence = [log_name]
    return [
        stage("dependencies", dependency_status, dependency_detail, evidence),
        stage(
            "compile",
            compile_status,
            "Gradle main source compilation task outcome.",
            evidence,
        ),
        stage(
            "unit-tests",
            tests_status,
            "Gradle test task outcome. NO-SOURCE, up-to-date and cached tasks are skipped.",
            evidence,
        ),
        stage(
            "build",
            build_status,
            f"Gradle build exit code {result.returncode}.",
            evidence,
        ),
    ], artifacts


def _build_unavailable(
    status: str, detail: str, evidence: list[str] | None = None
) -> list[dict[str, Any]]:
    return [
        stage(name, status, detail, evidence)
        for name in ("dependencies", "compile", "unit-tests", "build")
    ]


def _manual_checks(workspace: Path, evidence: Path | None) -> list[dict[str, Any]]:
    entries = {} if evidence is None else read_json(safe_path(evidence))
    if not isinstance(entries, dict) or set(entries).difference(MANUAL_STAGES):
        raise ValueError(
            "Evidence must be a JSON object keyed by dedicated-server, client, or gameplay."
        )
    results = []
    for identifier in MANUAL_STAGES:
        if identifier not in entries:
            results.append(
                stage(
                    identifier, "skipped", "No runtime or gameplay evidence supplied."
                )
            )
            continue
        entry = entries[identifier]
        if (
            not isinstance(entry, dict)
            or set(entry) != {"status", "detail", "path"}
            or entry["status"]
            not in ("passed", "failed", "skipped", "blocked", "not available")
            or not isinstance(entry["detail"], str)
            or not entry["detail"].strip()
            or not isinstance(entry["path"], str)
        ):
            raise ValueError(
                f"Invalid evidence entry for {identifier}; expected status, detail and path."
            )
        path = inside(workspace, entry["path"])
        fingerprint = _sha256(path)
        if path.stat().st_size == 0:
            raise ValueError(f"Empty verification evidence: {entry['path']}")
        result = stage(
            identifier,
            entry["status"],
            entry["detail"],
            [f"{entry['path']} (SHA-256 {fingerprint})"],
        )
        result["provenance"] = "external"
        results.append(result)
    return results


def verify(
    workspace: Path,
    state: dict,
    *,
    run_gradle: bool = False,
    gradle: Path | None = None,
    evidence: Path | None = None,
    timeout: int = 300,
    runtime: dict[str, str] | None = None,
    parity_task: str | None = None,
    baseline: Path | None = None,
    baseline_java: Path | None = None,
) -> dict[str, Any]:
    """Verify a locked migration workspace and return serializable stage results."""
    workspace = safe_path(workspace)
    if timeout <= 0:
        raise ValueError("Verification timeout must be positive.")
    if (runtime or parity_task) and not run_gradle:
        raise ValueError(
            "Runtime and parity probes require authorized Gradle execution."
        )
    if bool(parity_task) != bool(baseline):
        raise ValueError("Parity requires a task and a disposable baseline copy.")
    if baseline is not None:
        baseline = _validate_baseline(workspace, state, baseline)
    target = state["plan"]["target"]
    manual = _manual_checks(workspace, evidence)
    inventory = scan(workspace)
    checks = _offline_checks(workspace, inventory, target)
    artifacts: list[dict[str, str]] = []
    if target["engine"] != "minecraft":
        build = _build_unavailable("not available", "No build adapter for this engine.")
    elif not run_gradle:
        build = _build_unavailable(
            "skipped", "Project build execution was not enabled."
        )
    elif inventory["environment"]["build"]["value"] != "gradle":
        build = _build_unavailable("not available", "No Gradle project detected.")
    else:
        build, artifacts = _gradle_checks(workspace, gradle=gradle, timeout=timeout)
    if (runtime or parity_task) and target["engine"] == "minecraft":
        probes = _probe_checks(
            workspace,
            gradle,
            timeout,
            runtime or {},
            parity_task,
            baseline,
            baseline_java,
        )
        if baseline is not None and snapshot(baseline) != state["baseline"]:
            probes["gameplay"] = stage(
                "gameplay",
                "failed",
                "The probe changed baseline project inputs.",
                probes["gameplay"]["evidence"],
            )
        manual = [probes.get(entry["id"], entry) for entry in manual]
    return {"stages": checks + build + manual, "artifacts": artifacts}


def _probe_checks(
    workspace: Path,
    gradle: Path | None,
    timeout: int,
    runtime: dict[str, str],
    parity_task: str | None,
    baseline: Path | None,
    baseline_java: Path | None,
) -> dict[str, dict]:
    stages = {}
    tasks = {"client": "runClient", "dedicated-server": "runServer"}
    if not runtime.keys() <= tasks.keys() or any(
        not MARKER.fullmatch(marker) for marker in runtime.values()
    ):
        raise ValueError("Runtime readiness markers must be single uppercase tokens")
    if parity_task and not TASK_NAME.fullmatch(parity_task):
        raise ValueError("Expected an unqualified Gradle parity task name")
    executable = _gradle_path(workspace, gradle)
    for name, marker in runtime.items():
        if name == "dedicated-server" and not _server_eula(workspace):
            stages[name] = stage(
                name,
                "blocked",
                "Supply an accepted eula.txt in the disposable run/server directory.",
            )
        elif executable is None:
            stages[name] = stage(name, "blocked", "Gradle launcher was not found.")
        else:
            probe = check_readiness(
                run_probe(workspace, workspace, executable, tasks[name], timeout),
                workspace,
                marker,
            )
            stages[name] = stage(name, probe.status, probe.detail, [probe.log])
    if parity_task and baseline is not None:
        original_gradle = _gradle_path(baseline, gradle)
        stages["gameplay"] = stage(
            "gameplay", "blocked", "A Gradle launcher is required for both projects."
        )
        if original_gradle is not None and executable is not None:
            stages["gameplay"] = _parity_check(
                workspace,
                baseline,
                executable,
                original_gradle,
                parity_task,
                timeout,
                baseline_java,
            )
    return stages


def _validate_baseline(workspace: Path, state: dict, baseline: Path) -> Path:
    baseline = safe_path(baseline)
    source = Path(state["plan"]["source"]["source"])
    if any(
        baseline.is_relative_to(root) or root.is_relative_to(baseline)
        for root in (source, workspace)
    ):
        raise ValueError(
            "Parity requires a disposable baseline copy disjoint from source and target"
        )
    if not baseline.is_dir() or snapshot(baseline) != state["baseline"]:
        raise ValueError("Parity baseline does not match the original migration inputs")
    return baseline


def _server_eula(workspace: Path) -> bool:
    eula = inside(workspace, "run/server/eula.txt", missing=True)
    if not eula.is_file():
        return False
    values = re.findall(
        r"(?m)^\s*eula\s*=\s*(\w+)[ \t]*\r?$", _read_regular(eula, 4096).decode("utf-8")
    )
    return values == ["true"]


def _parity_check(
    workspace: Path,
    baseline: Path,
    gradle: Path,
    original_gradle: Path,
    task: str,
    timeout: int,
    baseline_java: Path | None,
) -> dict:
    original = run_probe(
        baseline, workspace, original_gradle, task, timeout, java_home=baseline_java
    )
    migrated = run_probe(workspace, workspace, gradle, task, timeout)
    logs = [original.log, migrated.log]
    for side, probe in (("Source", original), ("Target", migrated)):
        if probe.status != "passed":
            return stage(
                "gameplay", probe.status, f"{side} probe: {probe.detail}", logs
            )
    try:
        before, after, differences = parity(*(inside(workspace, name) for name in logs))
    except ValueError as error:
        return stage("gameplay", "failed", str(error), logs)
    result = stage(
        "gameplay",
        "failed" if differences else "passed",
        f"{len(differences)} differing observations"
        if differences
        else f"{len(before)} matching observations from {task}",
        logs,
    )
    result.update(
        provenance="paired Gradle probe",
        source=before,
        target=after,
        differences=differences,
    )
    return result
