"""Target capability assessment and structured migration plans."""

import re
from dataclasses import asdict, dataclass
from importlib.resources import files
from pathlib import Path
from typing import Protocol

from .io import digest, json_load, safe_path
from .rules import Rule
from .scan import scan

SYSTEMS = {
    "world": "Compare world access, chunk availability, dimensions and ownership of mutations.",
    "scheduling": "Compare tick scheduling, lifetime, threading and cancellation.",
    "initialization": "Compare entrypoints, sidedness and lifecycle order.",
    "registries": "Preserve registry IDs and compare registration phases.",
    "blocks": "Compare placement, state properties, ticks, drops and block entities.",
    "items": "Compare registration, stack data and use behavior.",
    "entities": "Compare registration, spawning, AI, attributes and synchronization.",
    "world-generation": "Compare codecs, dimensions and generation on a fresh disposable world.",
    "events": "Compare timing, ordering, threading and cancellation semantics.",
    "networking": "Revisit payload codecs, direction, negotiation and scheduling.",
    "rendering": "Compare render callbacks, model assets and client-only class loading.",
    "guis": "Compare menu synchronization, input and client/server responsibilities.",
    "configuration": "Compare defaults, accepted values and legacy configuration loading.",
    "persistence": "Test an upgraded copy of a representative save, including reload and restart.",
    "commands": "Compare dispatch, permissions, suggestions and client/server feedback.",
    "data-packs": "Check format versions, recipes, tags, loot and resource reload.",
    "resources": "Check asset formats, identifiers, paths and resource reload.",
    "mixins": "Resolve exact target owners, descriptors, injection points and sides.",
    "access-transformers": "Review transformed member visibility against target mappings.",
    "access-wideners": "Review namespace, member descriptors and access rules.",
    "integrations": "Check dependency availability and behavior with and without optional integrations.",
}
CAPABILITIES = {"direct", "adaptable", "requires-reimplementation", "unsupported"}


@dataclass(frozen=True)
class Target:
    engine: str
    loader: str | None
    version: str | None
    mappings: str | None
    java: int | None
    mode: str
    reference: str


class TargetAdapter(Protocol):
    def assess(self, subsystem: str) -> str: ...


@dataclass(frozen=True)
class JavaAdapter:
    same_loader: bool

    def assess(self, subsystem: str) -> str:
        return "adaptable" if self.same_loader else "requires-reimplementation"


@dataclass(frozen=True)
class EngineAdapter:
    capabilities: dict[str, str]

    def assess(self, subsystem: str) -> str:
        return self.capabilities.get(subsystem, "unsupported")


def target_profiles() -> dict:
    profiles = json_load(
        files("modstride").joinpath("data", "targets.json").read_bytes()
    )
    validate_target_profiles(profiles)
    return profiles


def validate_target_profiles(profiles: dict) -> None:
    try:
        if (
            type(profiles["schema_version"]) is not int
            or profiles["schema_version"] != 1
        ):
            raise ValueError("Unsupported target profile schema")
        if any(
            type(java) is not int or java < 1 for java in profiles["versions"].values()
        ):
            raise ValueError("Invalid Java version in target profile")
        for profile in profiles["loaders"].values():
            if profile["mode"] not in {"assisted", "assessment"} or not profile[
                "reference"
            ].startswith("https://"):
                raise ValueError("Invalid loader profile")
        for profile in profiles["engines"].values():
            if (
                profile["mode"] != "experimental-assessment"
                or not profile["reference"].startswith("https://")
                or not profile["capabilities"].keys() <= SYSTEMS.keys()
                or not set(profile["capabilities"].values()) <= CAPABILITIES
            ):
                raise ValueError("Invalid engine profile")
        for route in profiles["demonstrated"]:
            if (
                route["loader"] not in profiles["loaders"]
                or not {route["source"], route["target"]} <= profiles["versions"].keys()
                or not route["mappings"]
            ):
                raise ValueError("Invalid demonstrated route")
    except (AttributeError, KeyError, TypeError) as error:
        raise ValueError("Malformed target profile catalogue") from error


def resolve_target(
    version: str | None, loader: str | None, engine: str, mappings: str | None
) -> Target:
    profiles = target_profiles()
    if version and not re.fullmatch(r"[0-9][0-9A-Za-z._+-]{0,39}", version):
        raise ValueError("Invalid target version")
    if engine != "minecraft":
        if engine not in profiles["engines"] or loader or mappings:
            raise ValueError(
                "Experimental engine assessment requires a known engine and no loader or mappings"
            )
        profile = profiles["engines"][engine]
        return Target(
            engine, None, version, None, None, profile["mode"], profile["reference"]
        )
    if loader not in profiles["loaders"] or not version:
        raise ValueError(
            "Minecraft targets require --to-version and --to-loader fabric|forge|neoforge|quilt"
        )
    if mappings not in {None, "mojang", "yarn", "intermediary", "mcp", "srg", "quilt"}:
        raise ValueError(f"Unknown target mapping namespace: {mappings}")
    profile = profiles["loaders"][loader]
    return Target(
        engine,
        loader,
        version,
        mappings,
        profiles["versions"].get(version),
        profile["mode"] if version in profiles["versions"] else "assessment",
        profile["reference"],
    )


def environment(inventory: dict, *, confirmed: bool = False) -> dict:
    result = {"engine": "minecraft"}
    for field, key in (
        ("minecraft", "version"),
        ("loader", "loader"),
        ("mappings", "mappings"),
    ):
        fact = inventory["environment"][field]
        result[key] = (
            fact["value"]
            if not confirmed or fact["confidence"] == "confirmed"
            else None
        )
    return result


def _release(version: str | None) -> tuple[int, int] | None:
    match = re.fullmatch(r"1\.(\d+)(?:\.(\d+))?", version or "")
    return (int(match[1]), int(match[2] or 0)) if match else None


def strategy(source: dict, target: Target) -> tuple[str, str]:
    if target.engine != "minecraft":
        return (
            "semantic-reimplementation",
            "Assess engine APIs and resources before selecting equivalents.",
        )
    old, new = _release(source["version"]), _release(target.version)
    if source["loader"] and source["loader"] != target.loader:
        return (
            "replacement-apis",
            "Resolve lifecycle, dependency and platform seams before rewriting affected subsystems.",
        )
    if old and new and abs(new[0] - old[0]) >= 4:
        return (
            "staging-assessment",
            "Compare a direct port with a targeted intermediate milestone for removed APIs or save conversion.",
        )
    if old and new and source["loader"]:
        return (
            "direct",
            "Research the target toolchain and adapt affected features in dependency order.",
        )
    return (
        "research-first",
        "Resolve the source version, mappings and loader before choosing a port strategy.",
    )


def _operation(
    id: str,
    title: str,
    kind: str,
    dependencies: list[str],
    criteria: str,
    *,
    status="pending",
    **details,
) -> dict:
    return {
        "id": id,
        "title": title,
        "kind": kind,
        "status": status,
        "dependencies": dependencies,
        "verification": [criteria],
        **details,
    }


def make_plan(source: Path, target: Target, rules: dict[str, Rule]) -> dict:
    source = safe_path(source)
    inventory = scan(source)
    observed = environment(inventory)
    confirmed = environment(inventory, confirmed=True)
    if (
        target.engine == "minecraft"
        and target.loader == confirmed["loader"]
        and not target.mappings
    ):
        # Retaining an exact, detected namespace is the default for same-loader plans.
        target = Target(
            target.engine,
            target.loader,
            target.version,
            confirmed["mappings"],
            target.java,
            target.mode,
            target.reference,
        )
    desired = asdict(target)
    selected_strategy, rationale = strategy(observed, target)
    adapter: TargetAdapter = JavaAdapter(observed["loader"] == target.loader)
    if target.engine != "minecraft":
        adapter = EngineAdapter(
            target_profiles()["engines"][target.engine]["capabilities"]
        )

    research = "research-target"
    operations = [
        _operation(
            research,
            "Review target toolchain and dependencies",
            "manual",
            [],
            "Record version-pinned source or official documentation for the target and each dependency.",
        )
    ]
    automated = []
    deferred = []
    for rule in rules.values():
        if not rule.matches(confirmed, desired):
            continue
        if rule.data["status"] != "trusted" or inventory["kind"] != "directory":
            deferred.append(
                {
                    "rule": rule.id,
                    "reason": "Requires reviewed rules and a source directory.",
                }
            )
            continue
        try:
            path, before, after = rule.prepare(source)
        except (OSError, ValueError) as error:
            deferred.append({"rule": rule.id, "reason": str(error)})
            continue
        if before == after:
            deferred.append(
                {
                    "rule": rule.id,
                    "reason": "The target value is already present in the source.",
                }
            )
            continue
        automated.append(
            _operation(
                rule.id,
                rule.data["title"],
                "rule",
                [],
                rule.data["postconditions"][0],
                rule_fingerprint=rule.fingerprint,
                path=path.relative_to(source).as_posix(),
                before=digest(before),
                after=digest(after),
            )
        )
    operations.extend(automated)
    setup = "review-build"
    operations.append(
        _operation(
            setup,
            "Review build, loader and mapping configuration",
            "manual",
            [research, *(entry["id"] for entry in automated)],
            "Confirm dependency versions, Gradle/JDK support, loader metadata and production remapping.",
        )
    )
    matrix = []
    found = inventory["subsystems"]
    for name, guidance in SYSTEMS.items():
        detected = found.get(name, [])
        applicability = adapter.assess(name)
        risk = (
            "review"
            if not detected
            else (
                "high"
                if selected_strategy != "direct"
                or name
                in {
                    "persistence",
                    "networking",
                    "mixins",
                    "world-generation",
                    "rendering",
                }
                else "medium"
            )
        )
        matrix.append(
            {
                "subsystem": name,
                "risk": risk,
                "assessment": applicability,
                "signals": detected,
                "guidance": guidance,
            }
        )
        if detected or name == "initialization":
            operations.append(
                _operation(
                    "review-" + name, f"Review {name}", "manual", [setup], guidance
                )
            )
    operations.append(
        _operation(
            "verify-port",
            "Verify build, runtime and gameplay parity",
            "verification",
            [operation["id"] for operation in operations],
            "Capture independent compile, client/server boot and source-vs-target feature evidence.",
        )
    )
    return {
        "schema_version": 1,
        "source": inventory,
        "target": desired,
        "strategy": selected_strategy,
        "rationale": rationale,
        "compatibility": matrix,
        "operations": operations,
        "deferred_rules": deferred,
        "limitations": [
            "Static signals are incomplete and require source review.",
            "A matching configuration rule does not establish dependency, API or gameplay compatibility.",
        ],
    }


def validate_plan(plan) -> dict:
    if (
        not isinstance(plan, dict)
        or type(plan.get("schema_version")) is not int
        or plan["schema_version"] != 1
    ):
        raise ValueError("Unsupported migration plan schema")
    try:
        source, target, operations = plan["source"], plan["target"], plan["operations"]
        resolved = resolve_target(
            target["version"], target["loader"], target["engine"], target["mappings"]
        )
        if target != asdict(resolved) or not Path(source["source"]).is_absolute():
            raise ValueError("Invalid target or source path in plan")
        if source["kind"] not in {"directory", "jar"} or not isinstance(
            operations, list
        ):
            raise ValueError("Invalid migration source or operations")
        seen = set()
        for operation in operations:
            op_id = operation["id"]
            if not re.fullmatch(r"[a-z][a-z0-9-]{2,79}", op_id) or op_id in seen:
                raise ValueError("Invalid or duplicate operation ID")
            if (
                operation["kind"] not in {"rule", "manual", "verification"}
                or operation["status"] != "pending"
            ):
                raise ValueError(f"Invalid operation kind or status for {op_id}")
            if (
                not isinstance(operation["dependencies"], list)
                or not set(operation["dependencies"]) <= seen
            ):
                raise ValueError(f"Invalid dependencies for {op_id}")
            if (
                not isinstance(operation["verification"], list)
                or not operation["verification"]
            ):
                raise ValueError(f"Missing verification criteria for {op_id}")
            if operation["kind"] == "rule":
                for key in ("rule_fingerprint", "before", "after"):
                    if not re.fullmatch(r"[0-9a-f]{64}", operation[key]):
                        raise ValueError(f"Invalid {key} for {op_id}")
            seen.add(op_id)
    except (KeyError, AttributeError, TypeError) as error:
        raise ValueError("Malformed migration plan") from error
    return plan
