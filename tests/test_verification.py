import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from modstride import verification

SAMPLE = Path(__file__).parents[1] / "examples/sample-source-mod"


@pytest.fixture
def project(tmp_path):
    workspace = tmp_path / "project with spaces"
    shutil.copytree(SAMPLE, workspace)
    (workspace / ".modstride").mkdir()
    state = {
        "plan": {
            "target": {"engine": "minecraft", "loader": "fabric", "version": "1.20.1"}
        }
    }
    return workspace, state


def by_stage(result):
    return {item["id"]: item for item in result["stages"]}


def test_default_verify_does_not_execute_build(project, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Build ran without explicit opt-in")

    monkeypatch.setattr(verification.subprocess, "run", unexpected)
    workspace, state = project
    result = verification.verify(workspace, state)
    stages = by_stage(result)
    assert stages["target"]["status"] == "passed"
    assert stages["metadata"]["status"] == "passed"
    assert stages["resources"]["status"] == "passed"
    assert stages["build"]["status"] == "skipped"
    assert stages["gameplay"]["status"] == "skipped"
    assert result["artifacts"] == []


def test_target_mismatch_and_invalid_resource(project):
    workspace, state = project
    state["plan"]["target"]["version"] = "1.20.4"
    invalid = workspace / "src/main/resources/assets/modstride_example/lang/en_us.json"
    invalid.write_text("not JSON", encoding="utf-8")
    stages = by_stage(verification.verify(workspace, state))
    assert stages["target"]["status"] == "failed"
    assert stages["resources"]["status"] == "failed"
    assert "en_us.json" in stages["resources"]["evidence"][0]


def test_bad_fabric_metadata(project):
    workspace, state = project
    (workspace / "src/main/resources/fabric.mod.json").write_text(
        '{"schemaVersion": true, "id": "modstride_example", "version": "1.0.0"}',
        encoding="utf-8",
    )
    stages = by_stage(verification.verify(workspace, state))
    assert stages["metadata"]["status"] == "failed"


def test_missing_gradle_launcher(project):
    workspace, state = project
    stages = by_stage(
        verification.verify(
            workspace, state, run_gradle=True, gradle=workspace / "missing.exe"
        )
    )
    assert stages["build"]["status"] == "blocked"
    assert stages["compile"]["status"] == "blocked"
    assert stages["dependencies"]["status"] == "blocked"


@pytest.mark.parametrize(
    ("output", "exit_code", "dependencies", "compile_status", "tests", "build"),
    [
        (
            "> Task :compileJava\n> Task :test NO-SOURCE\n> Task :remapJar\n",
            0,
            "passed",
            "passed",
            "skipped",
            "passed",
        ),
        (
            "Could not resolve all files for configuration ':minecraft'.\n",
            1,
            "failed",
            "blocked",
            "blocked",
            "failed",
        ),
        (
            "> Task :compileJava UP-TO-DATE\n> Task :test FROM-CACHE\n> Task :jar UP-TO-DATE\n",
            0,
            "passed",
            "passed",
            "skipped",
            "passed",
        ),
        (
            "> Task :compileJava FAILED\nerror: cannot find symbol\n",
            1,
            "not available",
            "failed",
            "blocked",
            "failed",
        ),
    ],
)
def test_gradle_evidence(
    project, monkeypatch, output, exit_code, dependencies, compile_status, tests, build
):
    workspace, state = project
    launcher = workspace / "reviewed gradle.exe"
    launcher.touch()
    folder = workspace / "build/libs"
    folder.mkdir(parents=True)
    (folder / "sample.jar").write_bytes(b"old build")

    def execute(command, *, cwd, stdout, **kwargs):
        assert command == [str(launcher), "--no-daemon", "--console=plain", "build"]
        assert cwd == workspace
        if not exit_code and "UP-TO-DATE" not in output:
            (folder / "sample.jar").write_bytes(b"new build")
        stdout.write(output.encode())
        return SimpleNamespace(returncode=exit_code)

    monkeypatch.setattr(verification.subprocess, "run", execute)
    result = verification.verify(workspace, state, run_gradle=True, gradle=launcher)
    stages = by_stage(result)
    for name, status in {
        "dependencies": dependencies,
        "compile": compile_status,
        "unit-tests": tests,
        "build": build,
    }.items():
        assert stages[name]["status"] == status
        assert (workspace / stages[name]["evidence"][0]).read_text() == output
    if build == "passed" and "UP-TO-DATE" not in output:
        assert result["artifacts"][0]["path"] == "build/libs/sample.jar"
        assert len(result["artifacts"][0]["sha256"]) == 64
    else:
        assert result["artifacts"] == []


def test_manual_evidence_is_attributed_and_requires_workspace_file(project):
    workspace, state = project
    note = workspace / "parity notes.txt"
    note.write_text(
        "Both disposable worlds allowed the item to stack to 16.", encoding="utf-8"
    )
    evidence = workspace / "evidence.json"
    entry = {
        "status": "passed",
        "detail": "Compared inventory stacks",
        "path": note.name,
    }
    evidence.write_text(json.dumps({"gameplay": entry}), encoding="utf-8")
    stages = by_stage(verification.verify(workspace, state, evidence=evidence))
    assert stages["gameplay"]["status"] == "passed"
    assert stages["gameplay"]["provenance"] == "external"
    assert note.name in stages["gameplay"]["evidence"][0]
    assert stages["dedicated-server"]["status"] == "skipped"

    entry["path"] = "../outside.log"
    evidence.write_text(json.dumps({"gameplay": entry}), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsafe relative path"):
        verification.verify(workspace, state, evidence=evidence)
