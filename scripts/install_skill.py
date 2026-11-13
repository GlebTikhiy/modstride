"""Copy, verify, or export the canonical modstride skill."""

from __future__ import annotations

import argparse
import shutil
import stat
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "modstride"


def source_files() -> dict[Path, Path]:
    return {
        path.relative_to(SKILL): path
        for path in sorted(SKILL.rglob("*"))
        if path.is_file()
    }


def is_link(path: Path) -> bool:
    attributes = getattr(path.lstat(), "st_file_attributes", 0)
    return path.is_symlink() or bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def differences(destination: Path, sources: dict[Path, Path]) -> list[str]:
    if not destination.is_dir() or is_link(destination):
        return [f"Expected a real skill directory at {destination}"]
    actual = {
        path.relative_to(destination): path
        for path in destination.rglob("*")
        if not path.is_dir() or is_link(path)
    }
    missing = [f"Missing {path}" for path in sorted(sources.keys() - actual.keys())]
    extra = [f"Extra {path}" for path in sorted(actual.keys() - sources.keys())]
    changed = [
        f"Changed {path}"
        for path in sorted(actual.keys() & sources.keys())
        if is_link(actual[path])
        or not actual[path].is_file()
        or actual[path].read_bytes() != sources[path].read_bytes()
    ]
    return missing + extra + changed


def install(destination: Path, sources: dict[Path, Path]) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for name, source in sources.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command, help_text in (
        ("install", "Install a copy into a skills directory"),
        ("check", "Compare an installed copy with the canonical skill"),
        ("export", "Write a standalone ZIP containing modstride/"),
    ):
        subcommand = commands.add_parser(command, help=help_text, description=help_text)
        subcommand.add_argument("path", type=Path)
    args = parser.parse_args()
    sources = source_files()
    try:
        if args.command == "export":
            with zipfile.ZipFile(args.path, "x", zipfile.ZIP_DEFLATED) as archive:
                for name, source in sources.items():
                    archive.write(source, Path(SKILL.name) / name)
            print(args.path)
            return 0

        destination = args.path / SKILL.name
        if args.command == "install" and not destination.exists():
            install(destination, sources)

        drift = differences(destination, sources)
        if drift:
            print("\n".join(drift), file=sys.stderr)
            print("Move the existing copy aside before reinstalling.", file=sys.stderr)
            return 1
        print(destination)
        return 0
    except OSError as error:
        print(f"Skill {args.command} failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
