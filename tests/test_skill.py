import re
import subprocess
import sys
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "modstride"
INSTALLER = ROOT / "scripts" / "install_skill.py"


def run_installer(command: str, path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INSTALLER), command, str(path)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_skill_references_are_packaged() -> None:
    prefix, frontmatter, instructions = (
        (SKILL / "SKILL.md").read_text(encoding="utf-8").split("---", 2)
    )
    metadata = yaml.safe_load(frontmatter)
    assert prefix == ""
    assert metadata["name"] == SKILL.name
    assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", metadata["name"])
    assert 0 < len(metadata["description"].strip()) <= 1024
    assert 0 < len(metadata["compatibility"].strip()) <= 500
    assert len(instructions.splitlines()) < 500
    references = set(re.findall(r"\]\((references/[^)]+)\)", instructions))
    assert references
    assert references == {
        path.relative_to(SKILL).as_posix()
        for path in (SKILL / "references").glob("*.md")
    }
    assert (SKILL / "LICENSE").read_text() == (ROOT / "LICENSE").read_text()


def test_skill_install_and_drift(tmp_path: Path) -> None:
    skills_dir = tmp_path / "Mod With Spaces" / ".agents" / "skills"
    result = run_installer("install", skills_dir)
    assert result.returncode == 0, result.stderr
    assert run_installer("install", skills_dir).returncode == 0
    assert run_installer("check", skills_dir).returncode == 0

    installed = skills_dir / "modstride" / "SKILL.md"
    installed.write_text("local changes", encoding="utf-8")
    drift = run_installer("check", skills_dir)
    assert drift.returncode == 1
    assert "Changed SKILL.md" in drift.stderr
    assert run_installer("install", skills_dir).returncode == 1
    assert installed.read_text(encoding="utf-8") == "local changes"


def test_export_is_a_standalone_skill(tmp_path: Path) -> None:
    package = tmp_path / "skill archive.zip"
    result = run_installer("export", package)
    assert result.returncode == 0, result.stderr
    destination = tmp_path / ".claude" / "skills"
    with zipfile.ZipFile(package) as archive:
        archive.extractall(destination)
    assert run_installer("check", destination).returncode == 0
    assert run_installer("export", package).returncode == 1
