import json
import shutil
from pathlib import Path

import pytest

from modstride.cli import main
from modstride.planning import make_plan, resolve_target, validate_plan
from modstride.rules import load_rules

SAMPLE = Path(__file__).resolve().parents[1] / "examples" / "counter-source-mod"
RULE = "fabric-1206-counter-custom-data"


def test_preexisting_assessment_plan_remains_valid():
    target = resolve_target("1.20.6", "fabric", "minecraft", None)
    plan = make_plan(SAMPLE, target, {})
    plan["target"].update(java=None, mode="assessment")
    assert validate_plan(plan) is plan


def test_counter_java_rule_preserves_line_endings_and_rejects_drift():
    rule = load_rules()[RULE]
    before = (SAMPLE / rule.data["path"]).read_bytes().replace(b"\r\n", b"\n")
    for eol in (b"\n", b"\r\n"):
        original = b"\xef\xbb\xbf" + before.replace(b"\n", eol)
        migrated = rule.transform(original)
        assert migrated.startswith(b"\xef\xbb\xbf")
        assert b"CustomData.update(DataComponents.CUSTOM_DATA" in migrated
        assert b"getOrCreateTag" not in migrated
        assert migrated.count(eol) == original.count(eol) + 1
        assert rule.transform(migrated) == migrated
    with pytest.raises(ValueError, match="exact reviewed Java"):
        rule.transform(before.replace(b"stack.getTag()", b"stack.getOrCreateTag()"))
    with pytest.raises(ValueError, match="mixed Java line endings"):
        rule.transform(before.replace(b"\n", b"\r\n", 1))


def test_counter_end_to_end_and_interrupted_java_rule(tmp_path):
    source = tmp_path / "source"
    shutil.copytree(SAMPLE, source)
    rules = load_rules()
    source_java = source / rules[RULE].data["path"]
    original = source_java.read_bytes()
    target = resolve_target("1.20.6", "fabric", "minecraft", None)
    source_java.write_bytes(original + b"// Project-specific storage change.\n")
    drift = make_plan(source, target, rules)
    assert RULE not in {item["id"] for item in drift["operations"]}
    assert RULE in {item["rule"] for item in drift["deferred_rules"]}
    source_java.write_bytes(original)

    plan = tmp_path / "plan"
    workspace = tmp_path / "counter port"
    assert (
        main(
            [
                "plan",
                str(source),
                "--to-loader",
                "fabric",
                "--to-version",
                "1.20.6",
                "--output-dir",
                str(plan),
            ]
        )
        == 0
    )
    apply = [
        "apply",
        "--plan",
        str(plan / "migration-plan.json"),
        "--workspace",
        str(workspace),
    ]
    assert main([*apply, "--dry-run"]) == 0
    assert not workspace.exists()
    assert main(apply) == 0
    assert source_java.read_bytes() == original
    assert (
        "CustomData.update" in (workspace / source_java.relative_to(source)).read_text()
    )
    assert "java_version=21" in (workspace / "gradle.properties").read_text()
    assert (
        "fabric_api_version=0.100.8+1.20.6"
        in (workspace / "gradle.properties").read_text()
    )
    state_path = workspace / ".modstride/state.json"
    state = json.loads(state_path.read_bytes())
    assert len(state["completed"]) == 3
    del state["completed"][RULE]
    state_path.write_text(json.dumps(state), encoding="utf-8")
    assert main(["resume", "--workspace", str(workspace), "--apply"]) == 0
    state = json.loads(state_path.read_bytes())
    assert state["completed"][RULE]["action"] == "recovered"


def test_grouped_rule_rejects_partial_upgrade():
    rule = load_rules()["fabric-1206-gradle-toolchain"]
    original = (SAMPLE / "gradle.properties").read_bytes()
    assert rule.transform(rule.transform(original)) == rule.transform(original)
    with pytest.raises(ValueError, match="all reviewed source property values"):
        rule.transform(original.replace(b"java_version=17", b"java_version=21"))
