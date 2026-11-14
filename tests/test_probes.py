import sys
from pathlib import Path

import pytest

from modstride.probes import Probe, check_readiness, parity, run_probe
from modstride.verification import _probe_checks, _server_eula, _validate_baseline
from modstride.workspace import snapshot


def test_observations_require_all_scenarios_and_no_duplicates(tmp_path):
    source = tmp_path / "source.log"
    target = tmp_path / "target.log"
    source.write_text("MODSTRIDE_OBSERVATION first=1\nMODSTRIDE_OBSERVATION reload=2\n")
    target.write_text("[INFO]: MODSTRIDE_OBSERVATION first=1\n")
    assert parity(source, target)[2] == {"reload": {"source": 2, "target": None}}
    target.write_text(source.read_text())
    assert parity(source, target)[2] == {}
    target.write_text(source.read_text() + "MODSTRIDE_OBSERVATION first=1\n")
    with pytest.raises(ValueError, match="Duplicate"):
        parity(source, target)
    target.write_text("successful build\n")
    with pytest.raises(ValueError, match="No behavior"):
        parity(source, target)


def test_readiness_requires_marker_and_successful_exit(tmp_path):
    log = tmp_path / "probe.log"
    log.write_text("[INFO]: GAME_READY_EXTRA\n")
    assert (
        check_readiness(
            Probe("passed", "exit 0", log.name), tmp_path, "GAME_READY"
        ).status
        == "failed"
    )
    log.write_text("[00:00:01] [Render thread/INFO] (modstride-counter) GAME_READY\n")
    assert (
        check_readiness(
            Probe("passed", "exit 0", log.name), tmp_path, "GAME_READY"
        ).status
        == "passed"
    )
    assert (
        check_readiness(
            Probe("failed", "exit 1", log.name), tmp_path, "GAME_READY"
        ).status
        == "failed"
    )


def test_server_probe_never_accepts_eula(tmp_path):
    stages = _probe_checks(
        tmp_path, None, 1, {"dedicated-server": "SERVER_READY"}, None, None, None
    )
    assert stages["dedicated-server"]["status"] == "blocked"
    run = tmp_path / "run/server"
    assert not run.exists()
    run.mkdir(parents=True)
    (run / "eula.txt").write_text("eula=true\neula=false\n")
    assert not _server_eula(tmp_path)
    (run / "eula.txt").write_text("# accepted by operator\n eula = true\n")
    assert _server_eula(tmp_path)


def test_runtime_process_captures_failure_log(tmp_path):
    (tmp_path / ".modstride").mkdir()
    outcome = run_probe(tmp_path, tmp_path, Path(sys.executable), "runClient", 5)
    assert outcome.status == "failed"
    assert "no-daemon" in (tmp_path / outcome.log).read_text()


def test_baseline_requires_disjoint_copy_of_original_inputs(tmp_path):
    source, baseline, target = (
        tmp_path / name for name in ("source", "baseline", "target")
    )
    for directory in (source, baseline, target):
        directory.mkdir()
    (source / "build.gradle").write_text("original")
    (baseline / "build.gradle").write_text("original")
    state = {"plan": {"source": {"source": str(source)}}, "baseline": snapshot(source)}
    assert _validate_baseline(target, state, baseline) == baseline
    with pytest.raises(ValueError, match="disjoint"):
        _validate_baseline(target, state, source)
    (baseline / "build.gradle").write_text("changed")
    with pytest.raises(ValueError, match="does not match"):
        _validate_baseline(target, state, baseline)
