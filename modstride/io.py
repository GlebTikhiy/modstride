"""File boundaries shared by rule execution and workspace state."""

import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path


def json_load(raw: bytes | str):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key {key!r}")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f"Invalid JSON constant {value!r}")

    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)


def read_json(path: Path, limit: int = 16 * 1024 * 1024):
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError(f"JSON exceeds {limit} bytes: {path}")
    return json_load(raw)


def json_bytes(value) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def portable_parts(relative: str) -> list[str]:
    parts = relative.split("/")
    if any(
        part in {"", ".", ".."}
        or part.endswith((" ", "."))
        or re.search(r'[\\:<>"|?*\x00-\x1f]', part)
        or re.fullmatch(
            r"(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])", part.split(".")[0], re.I
        )
        for part in parts
    ):
        raise ValueError(f"Unsafe relative path: {relative!r}")
    return parts


def is_link(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def safe_path(path: Path, *, missing: bool = False) -> Path:
    """Check ancestors before following them, including Windows reparse points."""
    path = Path(os.path.abspath(path))
    for item in (*reversed(path.parents), path):
        try:
            info = item.lstat()
        except FileNotFoundError:
            if missing:
                continue
            raise
        if is_link(info):
            raise ValueError(
                f"Symlink or reparse point is outside the workspace contract: {item}"
            )
        if item != path and not stat.S_ISDIR(info.st_mode):
            raise ValueError(f"Expected a directory: {item}")
    return path


def inside(root: Path, relative: str, *, missing: bool = False) -> Path:
    return safe_path(root.joinpath(*portable_parts(relative)), missing=missing)


def atomic_write(path: Path, content: bytes) -> None:
    path = safe_path(path, missing=True)
    if path.exists() and not path.is_file():
        raise ValueError(f"Expected a regular file: {path}")
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            if path.exists():
                temporary.chmod(stat.S_IMODE(path.stat().st_mode))
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
