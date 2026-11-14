"""Run reviewed, finite Gradle probes and compare their observed behavior."""

import os
import re
import signal
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from .io import inside, safe_path

TASK_NAME = re.compile(r"[a-zA-Z][a-zA-Z0-9_]*")
MARKER = re.compile(r"[A-Z][A-Z0-9_]{2,79}")
OBSERVATION = re.compile(
    r"(?:^|\s)MODSTRIDE_OBSERVATION ([a-z][a-z0-9_-]*)=(-?\d{1,20})$"
)


@dataclass(frozen=True)
class Probe:
    status: str
    detail: str
    log: str


def gradle_launcher(executable: Path) -> Path:
    if os.name == "nt" and executable.suffix.lower() in {".bat", ".cmd"}:
        if re.search(r'[%!&^|<>"]', str(executable)):
            raise ValueError(
                "Gradle batch launcher path contains cmd.exe metacharacters"
            )
    return executable


def run_probe(
    workspace: Path,
    evidence_workspace: Path,
    executable: Path,
    task: str,
    timeout: int,
    *,
    java_home: Path | None = None,
) -> Probe:
    if not TASK_NAME.fullmatch(task):
        raise ValueError("Expected an unqualified Gradle task name")
    executable = gradle_launcher(executable)
    log_name = f".modstride/probe-{task}-{uuid.uuid4().hex}.log"
    log = inside(evidence_workspace, log_name, missing=True)
    env = None
    if java_home is not None:
        java_home = safe_path(java_home)
        java = inside(java_home, "bin/java.exe" if os.name == "nt" else "bin/java")
        if not java.is_file():
            raise ValueError("Baseline JAVA_HOME must contain a Java launcher")
        env = {**os.environ, "JAVA_HOME": str(java_home)}
    with log.open("xb") as stream:
        try:
            process = subprocess.Popen(
                [
                    str(executable),
                    "--no-daemon",
                    "--console=plain",
                    "--rerun-tasks",
                    task,
                ],
                cwd=workspace,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=os.name != "nt",
            )
        except OSError as error:
            return Probe("blocked", f"{task} could not start: {error}", log_name)
        try:
            code = process.wait(timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
            _stop(process)
            if isinstance(error, KeyboardInterrupt):
                raise
            return Probe("blocked", f"{task} exceeded {timeout}s", log_name)
    return Probe(
        "passed" if code == 0 else "failed", f"{task} exit code {code}", log_name
    )


def _stop(process: subprocess.Popen) -> None:
    if os.name == "nt":
        try:
            subprocess.run(
                [
                    str(Path(os.environ["SystemRoot"]) / "System32/taskkill.exe"),
                    "/PID",
                    str(process.pid),
                    "/T",
                    "/F",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=10)


def _log_lines(path: Path):
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            yield line.rstrip()


def check_readiness(probe: Probe, root: Path, marker: str) -> Probe:
    if not MARKER.fullmatch(marker):
        raise ValueError("Readiness marker must be a single uppercase token")
    if probe.status != "passed":
        return probe
    logged = re.compile(
        r"^\[[^\]]+\] \[[^\]]+\] \([^\r\n()]+\) " + re.escape(marker) + "$"
    )
    for line in _log_lines(inside(root, probe.log)):
        if line == marker or line.endswith(": " + marker) or logged.fullmatch(line):
            return Probe("passed", f"{probe.detail}; observed {marker}", probe.log)
    return Probe(
        "failed", f"{probe.detail}; readiness marker {marker} was absent", probe.log
    )


def observations(path: Path) -> dict[str, int]:
    values = {}
    for line in _log_lines(path):
        if match := OBSERVATION.search(line):
            name, value = match.groups()
            if name in values:
                raise ValueError(f"Duplicate behavior observation {name}")
            values[name] = int(value)
    if not values:
        raise ValueError("No behavior observations found")
    return values


def parity(source: Path, target: Path) -> tuple[dict[str, int], dict[str, int], dict]:
    before, after = observations(source), observations(target)
    differences = {
        key: {"source": before.get(key), "target": after.get(key)}
        for key in sorted(before.keys() | after.keys())
        if before.get(key) != after.get(key)
    }
    return before, after, differences
