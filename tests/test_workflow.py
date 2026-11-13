import copy
import json
import shutil
from pathlib import Path

import pytest

from modstride.cli import main
from modstride.io import json_bytes
from modstride.planning import make_plan, resolve_target
from modstride.rules import load_rules, validate_rule
from modstride.workspace import STATE_FILE, create_workspace

SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "sample-source-mod"


def test_original_sample(tmp_path, capsys):
    source = tmp_path / "original mod"
    shutil.copytree(SAMPLE, source)
    (source / "build").mkdir()
    (source / "build" / "generated.txt").write_text("generated")
    world = source / "custom save"
    world.mkdir()
    (world / "level.dat").write_text("real world marker")
    package = source / "src/main/java/example/world"
    package.mkdir(parents=True)
    (package / "Example.java").write_text("package example.world;")
    workspace = tmp_path / "ported mod"
    plan_dir = tmp_path / "plan output"
    assert main(["scan", str(source), "--format", "json"]) == 0
    facts = json.loads(capsys.readouterr().out)["environment"]
    assert facts["minecraft"]["value"] == "1.20.1"
    assert facts["mappings"]["confidence"] == "confirmed"

    assert (
        main(
            [
                "plan",
                str(source),
                "--to-version",
                "1.20.4",
                "--to-loader",
                "fabric",
                "--output-dir",
                str(plan_dir),
            ]
        )
        == 0
    )
    plan_path = plan_dir / "migration-plan.json"
    plan = json.loads(plan_path.read_bytes())
    assert plan["target"]["mappings"] == "mojang"
    assert (plan_dir / "MIGRATION_PLAN.md").is_file()
    assert (plan_dir / "COMPATIBILITY_MATRIX.md").is_file()
    assert sum(entry["kind"] == "rule" for entry in plan["operations"]) == 2

    apply_args = ["apply", "--plan", str(plan_path), "--workspace", str(workspace)]
    originals = {
        relative: (source / relative).read_bytes()
        for relative in ("gradle.properties", "src/main/resources/fabric.mod.json")
    }
    assert main([*apply_args, "--dry-run"]) == 0
    assert not workspace.exists()
    assert main(apply_args) == 0
    assert not (workspace / "build").exists()
    assert not (workspace / "custom save").exists()
    assert (workspace / package.relative_to(source) / "Example.java").is_file()
    for relative, before in originals.items():
        assert (source / relative).read_bytes() == before
        assert (workspace / relative).read_bytes() == before.replace(
            b"1.20.1", b"1.20.4"
        )

    args = ["--workspace", str(workspace)]
    state_path = workspace / STATE_FILE
    first = state_path.read_bytes()
    assert main(["resume", *args, "--apply"]) == 0
    assert state_path.read_bytes() == first
    assert main(apply_args) == 2
    state = json.loads(first)
    interrupted = state["completed"].pop("fabric-1204-gradle-minecraft")
    state_path.write_bytes(json_bytes(state))
    assert main(["resume", *args, "--apply"]) == 0
    recovered = json.loads(state_path.read_bytes())["completed"][
        "fabric-1204-gradle-minecraft"
    ]
    assert recovered == {**interrupted, "action": "recovered"}

    notes = workspace / "notes.md"
    notes.write_text("Version pinned official documentation and reviewed assumptions.")
    assert main(["resume", *args, "--record", "research-target", "notes.md"]) == 0
    assert main(["verify", *args]) == 0
    assert main(["report", *args]) == 0
    report = json.loads((workspace / ".modstride/migration-report.json").read_bytes())
    assert report["gameplay_parity"] == "skipped"
    assert report["progress"]["verification_stale"] is False
    assert "research-target" in report["progress"]["completed"]
    assert "verify-port" in {entry["id"] for entry in report["progress"]["pending"]}

    notes.write_text("Changed after evidence capture.")
    assert main(["report", *args]) == 0
    report = json.loads((workspace / ".modstride/migration-report.json").read_bytes())
    assert report["progress"]["verification_stale"] is True
    assert report["progress"]["changed_or_missing_evidence"] == ["research-target"]


def test_refuses_drift_overlap_and_existing_destination(tmp_path):
    source = tmp_path / "original"
    shutil.copytree(SAMPLE, source)
    rules = load_rules()
    plan = make_plan(
        source, resolve_target("1.20.4", "fabric", "minecraft", None), rules
    )
    for destination in (source, tmp_path, source / "nested"):
        with pytest.raises(ValueError, match="disjoint"):
            create_workspace(plan, destination, rules, dry_run=True)
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    with pytest.raises(ValueError, match="already exists"):
        create_workspace(plan, occupied, rules, dry_run=False)
    with (source / "gradle.properties").open("ab") as stream:
        stream.write(b"\n# changed after planning\n")
    with pytest.raises(ValueError, match="Input changed"):
        create_workspace(plan, tmp_path / "output", rules, dry_run=False)
    assert not (tmp_path / "output").exists()


def test_rule_preserves_bytes_and_rejects_ambiguous_syntax():
    rules = load_rules()
    prop = rules["fabric-1204-gradle-minecraft"]
    original = b"\xef\xbb\xbf# heading\r\nminecraft_version: 1.20.1\r\nmod_version=2.0"
    changed = original.replace(b"1.20.1", b"1.20.4")
    assert prop.transform(original) == changed
    assert prop.transform(changed) == changed
    for bad in (
        b"minecraft_version=1.20.1\nminecraft_version=1.20.1",
        b"minecraft_version=1.20.1\\\n 0",
        b"minecraft_version=1.20.2",
        b"minecraft_version=1.20.1\nminecraft_version 1.20.1",
    ):
        with pytest.raises(ValueError):
            prop.transform(bad)

    metadata = rules["fabric-1204-metadata-minecraft"]
    original = b'{\r\n\t"version": "1.20.1", "depends": {"minecraft" : "1.20.1"}\r\n}'
    expected = original.replace(b': "1.20.1"}', b': "1.20.4"}')
    assert metadata.transform(original) == expected
    assert metadata.transform(expected) == expected
    for bad in (
        b'{"depends":{"minecraft":"1.20.1","minecraft":"1.20.1"}}',
        b'{"depends":{"minecraft":["1.20.1"]}}',
        b'{"depends":{"minecraft":"~1.20.1"}}',
    ):
        with pytest.raises(ValueError):
            metadata.transform(bad)


def test_rule_schema_conflicts_and_proposed_rules(tmp_path):
    rules = load_rules()
    original = rules["fabric-1204-gradle-minecraft"]
    for unsafe in (
        "../gradle.properties",
        r"C:\gradle.properties",
        "CON/gradle.properties",
    ):
        candidate = {**original.data, "path": unsafe}
        with pytest.raises(ValueError):
            validate_rule(candidate)
    for bad in (True, 0, "1"):
        with pytest.raises(ValueError):
            validate_rule({**original.data, "schema_version": bad})
    duplicate = {**original.data, "id": "another-rule"}
    candidate_file = tmp_path / "rule.json"
    candidate_file.write_bytes(json_bytes(duplicate))
    with pytest.raises(ValueError, match="Conflicting"):
        load_rules(tmp_path)
    duplicate["status"] = "proposed"
    candidate_file.write_bytes(json_bytes(duplicate))
    plan = make_plan(
        SAMPLE,
        resolve_target("1.20.4", "fabric", "minecraft", None),
        load_rules(tmp_path),
    )
    assert "another-rule" not in {item["id"] for item in plan["operations"]}
    assert plan["deferred_rules"][0]["rule"] == "another-rule"


def test_assessment_paths_and_unknown_targets(tmp_path):
    rules = load_rules()
    target = resolve_target("1.21.1", "neoforge", "minecraft", None)
    plan = make_plan(SAMPLE, target, rules)
    assert plan["strategy"] == "replacement-apis"
    assert all(entry["kind"] != "rule" for entry in plan["operations"])
    horizon = make_plan(SAMPLE, resolve_target(None, None, "horizon", None), rules)
    assert horizon["target"]["mode"] == "experimental-assessment"
    assessments = {
        row["subsystem"]: row["assessment"] for row in horizon["compatibility"]
    }
    assert assessments["resources"] == "adaptable"
    assert assessments["items"] == "requires-reimplementation"
    assert (
        main(
            [
                "plan",
                str(SAMPLE),
                "--to-version",
                "1.20.4",
                "--to-loader",
                "fake",
                "--output-dir",
                str(tmp_path / "bad"),
            ]
        )
        == 2
    )
    assert (
        main(
            [
                "plan",
                str(SAMPLE),
                "--to-version",
                "1.20.4",
                "--to-loader",
                "fabric",
                "--to-mappings",
                "fabricated",
                "--output-dir",
                str(tmp_path / "bad"),
            ]
        )
        == 2
    )
    invalid = copy.deepcopy(plan)
    invalid["operations"][0]["dependencies"] = ["missing-operation"]
    with pytest.raises(ValueError, match="dependencies"):
        create_workspace(invalid, tmp_path / "bad", rules, dry_run=True)
