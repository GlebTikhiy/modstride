"""Validated, declarative rules with bounded field-level transformations."""

import json
import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from .io import digest, inside, json_bytes, json_load, portable_parts, read_json

KEY = re.compile(r"[a-zA-Z0-9_.-]+")
RULE_ID = re.compile(r"[a-z][a-z0-9-]{2,79}")
SELECTORS = {"engine", "loader", "version", "mappings"}
MAX_RULE_INPUT = 2 * 1024 * 1024
FIELDS = {
    "schema_version",
    "id",
    "title",
    "path",
    "source",
    "target",
    "confidence",
    "preconditions",
    "transformation",
    "postconditions",
    "behavioral_differences",
    "limitations",
    "references",
    "verification_evidence",
    "tests",
    "status",
}


@dataclass(frozen=True)
class Rule:
    data: dict

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def fingerprint(self) -> str:
        return digest(json_bytes(self.data))

    def matches(self, source: dict, target: dict) -> bool:
        return all(
            all(environment.get(key) == value for key, value in self.data[name].items())
            for name, environment in (("source", source), ("target", target))
        )

    def prepare(self, root: Path) -> tuple[Path, bytes, bytes]:
        path = inside(root, self.data["path"])
        if not path.is_file() or path.stat().st_size > MAX_RULE_INPUT:
            raise ValueError(
                f"Expected a regular rule input within {MAX_RULE_INPUT} bytes: {path}"
            )
        before = path.read_bytes()
        after = self.transform(before)
        if self.transform(after) != after:
            raise ValueError(f"Postcondition failed for {self.id}")
        return path, before, after

    def transform(self, raw: bytes) -> bytes:
        operation = self.data["transformation"]
        bom = raw.startswith(b"\xef\xbb\xbf")
        text = raw.decode("utf-8-sig")
        if operation["kind"] == "property":
            start, end, value = property_span(text, operation["key"])
            replacement = operation["after"]
        else:
            start, end, value = json_span(text, operation["keys"])
            replacement = '"' + operation["after"] + '"'
        if value == operation["after"]:
            return raw
        if value != operation["before"]:
            raise ValueError(
                f"{self.id} expected {operation['before']!r}, found {value!r}"
            )
        return (text[:start] + replacement + text[end:]).encode(
            "utf-8-sig" if bom else "utf-8"
        )


def property_span(text: str, key: str) -> tuple[int, int, str]:
    # This accepts a deliberately small subset of Java properties. A continuation,
    # escaped key or whitespace separator can hide a second definition.
    if re.search(r"(?m)\\\r?$", text) or "\r" in text.replace("\r\n", ""):
        raise ValueError("Unsupported Gradle properties continuation or line ending")
    assignments = []
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        stripped = line.lstrip(" \t\f")
        if stripped and not stripped.startswith(("#", "!")):
            match = re.fullmatch(r"[ \t]*([\w.-]+)[ \t]*[=:][ \t]*(.*)", line)
            if not match:
                raise ValueError("Expected literal key=value Gradle properties")
            if match[1] == key:
                assignments.append(
                    (offset + match.start(2), offset + match.end(2), match[2])
                )
        offset += len(raw_line)
    if len(assignments) != 1:
        raise ValueError(f"Expected one literal Gradle property {key!r}")
    return assignments[0]


def json_span(text: str, keys: list[str]) -> tuple[int, int, str]:
    """Locate a JSON field after strict parsing, preserving unrelated bytes."""
    json_load(text)
    decoder = json.JSONDecoder()
    whitespace = re.compile(r"[ \t\r\n]*")

    def skip(index: int) -> int:
        return whitespace.match(text, index).end()

    cursor = skip(0)
    for key in keys:
        if text[cursor : cursor + 1] != "{":
            raise ValueError(f"Expected object before JSON field {key!r}")
        cursor = skip(cursor + 1)
        while text[cursor : cursor + 1] != "}":
            name, end = decoder.raw_decode(text, cursor)
            cursor = skip(skip(end) + 1)
            if name == key:
                break
            _, end = decoder.raw_decode(text, cursor)
            cursor = skip(end)
            if text[cursor : cursor + 1] == ",":
                cursor = skip(cursor + 1)
        else:
            raise ValueError(f"Missing JSON field {key!r}")
    value, end = decoder.raw_decode(text, cursor)
    if not isinstance(value, str):
        raise ValueError(f"Expected string at JSON field {'.'.join(keys)}")
    return cursor, end, value


def _nonempty_strings(value) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and item.strip() for item in value)
    )


def validate_rule(data) -> Rule:
    if (
        not isinstance(data, dict)
        or set(data) != FIELDS
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
    ):
        raise ValueError("Rule must contain all schema version 1 fields")
    for key in (
        "id",
        "title",
        "path",
        "confidence",
        "status",
        "behavioral_differences",
    ):
        if not isinstance(data[key], str) or not data[key].strip():
            raise ValueError(f"Expected nonempty rule field {key}")
    if not RULE_ID.fullmatch(data["id"]):
        raise ValueError(f"Invalid rule ID: {data['id']}")
    path = portable_parts(data["path"])
    if any(part.startswith(".") for part in path):
        raise ValueError("Rule paths cannot target dotfiles or dot directories")
    for name in ("source", "target"):
        selector = data[name]
        if (
            not isinstance(selector, dict)
            or set(selector) != SELECTORS
            or not all(
                isinstance(value, str) and KEY.fullmatch(value)
                for value in selector.values()
            )
        ):
            raise ValueError(f"Invalid {name} rule selector")
    for key in (
        "preconditions",
        "postconditions",
        "limitations",
        "references",
        "verification_evidence",
        "tests",
    ):
        if not _nonempty_strings(data[key]):
            raise ValueError(f"Expected a nonempty list of strings for {key}")
    if not all(reference.startswith("https://") for reference in data["references"]):
        raise ValueError("Rule references must use HTTPS")
    if (
        data["status"] not in {"trusted", "proposed"}
        or data["confidence"] not in {"verified", "experimental"}
        or (data["status"] == "trusted" and data["confidence"] != "verified")
    ):
        raise ValueError("Trusted rules require verified confidence")
    operation = data["transformation"]
    if not isinstance(operation, dict):
        raise ValueError("Expected transformation object")
    kind = operation.get("kind")
    expected = {"kind", "before", "after"}
    if kind == "property" and path[-1] == "gradle.properties":
        expected.add("key")
        keys = [operation.get("key")]
    elif kind == "json-string" and path[-1] == "fabric.mod.json":
        expected.add("keys")
        keys = operation.get("keys")
    else:
        raise ValueError("Unsupported transformation or file")
    if (
        set(operation) != expected
        or not _nonempty_strings(keys)
        or not all(KEY.fullmatch(key) for key in keys)
    ):
        raise ValueError("Invalid transformation fields")
    if (
        not all(
            isinstance(operation[field], str) and KEY.fullmatch(operation[field])
            for field in ("before", "after")
        )
        or operation["before"] == operation["after"]
    ):
        raise ValueError("Expected different literal transformation values")
    return Rule(data)


def load_rules(extra: Path | None = None) -> dict[str, Rule]:
    catalogue = files("modstride").joinpath("data", "rules")
    inputs = [
        (item.name, json_load(item.read_bytes()))
        for item in sorted(catalogue.iterdir(), key=lambda item: item.name)
        if item.name.endswith(".json")
    ]
    if extra is not None:
        if not extra.is_dir():
            raise ValueError(f"Rule directory does not exist: {extra}")
        inputs.extend(
            (path.name, read_json(path)) for path in sorted(extra.glob("*.json"))
        )
    rules: dict[str, Rule] = {}
    destinations: set[tuple] = set()
    for filename, data in inputs:
        try:
            rule = validate_rule(data)
            if rule.id in rules:
                raise ValueError(f"Duplicate rule ID {rule.id}")
            signature = (
                tuple(sorted(data["source"].items())),
                tuple(sorted(data["target"].items())),
                data["path"].casefold(),
            )
            if data["status"] == "trusted":
                if signature in destinations:
                    raise ValueError(f"Conflicting trusted rules for {data['path']}")
                destinations.add(signature)
            rules[rule.id] = rule
        except ValueError as error:
            raise ValueError(f"{filename}: {error}") from error
    return rules
