"""Look up symbols in a user-supplied Tiny v2 mapping table."""

from pathlib import Path

from .io import safe_path

MAX_BYTES = 64 * 1024 * 1024
MAX_LINE = 32 * 1024


def lookup(
    mapping: Path,
    namespace: str,
    owner: str,
    member: str | None = None,
    descriptor: str | None = None,
) -> dict:
    """Match an exact name. JVM descriptors refer to the first namespace."""
    mapping = safe_path(mapping)
    if not mapping.is_file() or mapping.stat().st_size > MAX_BYTES:
        raise ValueError("Expected a regular Tiny v2 file within 64 MiB")
    if (member is None) != (descriptor is None):
        raise ValueError("Specify both --member and --descriptor, or neither")
    matches = []
    current = None
    with mapping.open("r", encoding="utf-8-sig") as stream:
        header = stream.readline(MAX_LINE + 1).rstrip("\r\n").split("\t")
        if header[:3] != ["tiny", "2", "0"] or len(header) < 5:
            raise ValueError("Expected a Tiny v2.0 header with two or more namespaces")
        namespaces = header[3:]
        if not all(namespaces) or len(set(namespaces)) != len(namespaces):
            raise ValueError("Invalid or duplicate Tiny namespace")
        if namespace not in namespaces:
            raise ValueError(
                f"Unknown mapping namespace {namespace!r}. Available: {', '.join(namespaces)}"
            )
        column = namespaces.index(namespace)
        while line := stream.readline(MAX_LINE + 1):
            if len(line) > MAX_LINE:
                raise ValueError("Tiny line exceeds lookup limit")
            if line.startswith("\tescaped-names"):
                raise ValueError(
                    "Tiny tables with escaped-names require an external mapping tool"
                )
            fields = line.rstrip("\r\n").split("\t")
            if fields[0] == "c":
                current = _names(namespaces, fields[1:])
                if member is None and current[namespace] == owner:
                    matches.append({"kind": "class", "owner": current})
            elif (
                current
                and current[namespace] == owner
                and fields[:2] in (["", "f"], ["", "m"])
            ):
                if len(fields) < 4:
                    raise ValueError("Malformed Tiny member row")
                names = _names(namespaces, fields[3:])
                if fields[2] == descriptor and fields[3 + column] == member:
                    matches.append(
                        {
                            "kind": "method" if fields[1] == "m" else "field",
                            "owner": current,
                            "names": names,
                            "descriptor": descriptor,
                            "descriptor_namespace": namespaces[0],
                        }
                    )
    if not matches:
        raise ValueError("No exact symbol match in the supplied table")
    if len(matches) != 1:
        raise ValueError("Ambiguous symbol in the supplied table")
    return {"mapping_file": str(mapping), **matches[0]}


def _names(namespaces: list[str], fields: list[str]) -> dict:
    if len(fields) != len(namespaces) or not fields[0]:
        raise ValueError("Invalid Tiny symbol row")
    return dict(zip(namespaces, (field or None for field in fields), strict=True))
