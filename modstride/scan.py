"""Static inventory of conventional Minecraft mod projects and JARs."""

from __future__ import annotations

import os
import re
import stat
import struct
import tomllib
import zipfile
import zlib
from collections import defaultdict
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree

from .io import is_link, json_load, safe_path

MAX_FILES = 25_000
MAX_TEXT_BYTES = 512 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_ARCHIVE_INDEX_BYTES = 4 * 1024 * 1024
IGNORED_DIRS = {
    ".git",
    ".gradle",
    ".idea",
    ".modstride",
    ".venv",
    ".vscode",
    "build",
    "out",
    "target",
    "run",
    "runs",
    "saves",
    "world",
    "world_nether",
    "world_the_end",
}
METADATA = {
    "fabric.mod.json": "fabric",
    "quilt.mod.json": "quilt",
    "META-INF/neoforge.mods.toml": "neoforge",
    "META-INF/mods.toml": "forge",
    "mcmod.info": "forge",
}
BUILD_FILES = {
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "gradle.properties",
    "pom.xml",
    "libs.versions.toml",
}
SOURCE_SUFFIXES = {".java", ".kt", ".scala"}
SUBSYSTEMS = {
    "initialization": r"\b(?:ModInitializer|ClientModInitializer|DedicatedServerModInitializer|FMLInitializationEvent|FMLCommonSetupEvent)\b|@Mod\s*\(",
    "registries": r"\b(?:Registry\.register|DeferredRegister|RegisterEvent|RegistryEvent|RegistryObject|BuiltInRegistries)\b",
    "blocks": r"\b(?:Block|BlockEntity|BlockState|TileEntity|BlockBehaviour)\b",
    "items": r"\b(?:Item|ItemStack|ItemGroup|CreativeModeTab)\b",
    "entities": r"\b(?:EntityType|EntityDataAccessor|SynchedEntityData|DataTracker|EntityAttribute)\b",
    "events": r"@SubscribeEvent\b|\b(?:EventBus|IEventBus|EVENT_BUS|EventFactory|ServerTickEvents|PlayerBlockBreakEvents)\b",
    "networking": r"\b(?:ClientPlayNetworking|ServerPlayNetworking|SimpleChannel|PacketDistributor|CustomPacketPayload|PayloadRegistrar|RegisterPayloadHandlersEvent)\b",
    "configuration": r"\b(?:ForgeConfigSpec|ModConfigSpec|AutoConfig|ClothConfig|ConfigSpec|ModConfig|Configuration)\b",
    "persistence": r"\b(?:SavedData|WorldSavedData|PersistentState|CompoundTag|NbtCompound|AttachmentType|CapabilityManager|DataComponentType)\b",
    "world-generation": r"\b(?:BiomeModifications|PlacedFeature|ConfiguredFeature|BiomeModifier|ChunkGenerator)\b",
    "rendering": r"\b(?:BlockEntityRenderer|EntityRenderer|EntityRendererRegistry|RenderLayer|RenderType|EntityRenderers)\b",
    "guis": r"\b(?:AbstractContainerMenu|ScreenHandler|AbstractContainerScreen|HandledScreen|MenuType)\b",
    "commands": r"\b(?:CommandRegistrationCallback|RegisterCommandsEvent|CommandDispatcher)\b",
    "mixins": r"@Mixin\b|\borg\.spongepowered\.asm\.mixin\b",
    "access-transformers": r"\baccessTransformer\b",
    "access-wideners": r"\baccessWidenerPath\b",
}
EXACT_RELEASE = re.compile(r"[0-9]+(?:\.[0-9]+){1,2}(?:-(?:pre|rc)[0-9]+)?")
PROPERTY_REFERENCE = re.compile(r"\$\{([\w.-]+)\}")
GRADLE_DEPENDENCY = re.compile(
    r"""^\s*(minecraft|mappings|(?:mod|test|compile|runtime|annotationProcessor|"""
    r"""implementation|api|include)[A-Za-z]*)\s*\(?\s*["']([^"'\n]+:[^"'\n]+)["']""",
    re.MULTILINE,
)


def _directory_files(root: Path, warnings: list[str]) -> list[str]:
    def walk_error(exc: OSError) -> None:
        warnings.append(f"Could not read directory: {exc}")

    result = []
    visited = 0
    for base, dirs, files in os.walk(root, onerror=walk_error):
        visited += len(dirs) + len(files)
        if visited > MAX_FILES:
            raise ValueError(
                f"Source directory exceeds {MAX_FILES:,} inventory entries"
            )
        base_path = Path(base)
        under_source = "src" in base_path.relative_to(root).parts
        safe_dirs = []
        for name in sorted(dirs):
            if not under_source and name.casefold() in IGNORED_DIRS:
                continue
            candidate = base_path / name
            if is_link(candidate.lstat()):
                warnings.append(
                    f"Skipped linked directory: {candidate.relative_to(root).as_posix()}"
                )
            elif not (candidate / "level.dat").exists():
                safe_dirs.append(name)
        dirs[:] = safe_dirs
        for name in sorted(files):
            candidate = base_path / name
            relative = candidate.relative_to(root).as_posix()
            info = candidate.lstat()
            if is_link(info) or not stat.S_ISREG(info.st_mode):
                warnings.append(f"Skipped linked or non-regular file: {relative}")
            else:
                result.append(relative)
    return sorted(result)


def _check_archive_index(root: Path) -> None:
    # Preflight the central-directory budget before ZipFile allocates its index.
    # Python's ZIP reader uses the final end-of-directory record in this tail.
    with root.open("rb") as stream:
        size = stream.seek(0, os.SEEK_END)
        stream.seek(max(0, size - (65_535 + 22)))
        tail = stream.read()
    offset = tail.rfind(b"PK\x05\x06")
    if offset < 0 or len(tail) - offset < 22:
        raise ValueError("Invalid JAR archive: missing end of central directory")
    _, disk, index_disk, local_count, count, length, index_offset, _ = (
        struct.unpack_from("<4s4H2IH", tail, offset)
    )
    absolute_offset = size - len(tail) + offset
    if absolute_offset >= 20:
        with root.open("rb") as stream:
            stream.seek(absolute_offset - 20)
            zip64 = stream.read(4) == b"PK\x06\x07"
        if zip64:
            raise ValueError(
                "ZIP64 JAR indexes are outside the scanner's archive limits"
            )
    if disk or index_disk or local_count != count:
        raise ValueError("Split JAR archives are unsupported")
    if count > MAX_FILES or length > MAX_ARCHIVE_INDEX_BYTES:
        raise ValueError("JAR central directory exceeds scanner limits")
    if index_offset + length > absolute_offset:
        raise ValueError(
            "Invalid JAR archive: central directory extends beyond its end record"
        )


def _archive_files(archive: zipfile.ZipFile, warnings: list[str]) -> list[str]:
    entries = archive.infolist()
    if len(entries) > MAX_FILES:
        raise ValueError(f"JAR exceeds {MAX_FILES:,} inventory entries")
    seen = set()
    files = []
    for entry in entries:
        name = entry.filename
        path = PurePosixPath(name)
        if (
            not name
            or name != entry.orig_filename
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in name
            or any(":" in part for part in path.parts)
            or name.rstrip("/") != path.as_posix()
            or stat.S_ISLNK(entry.external_attr >> 16)
        ):
            warnings.append(f"Skipped unsafe archive entry: {entry.orig_filename!r}")
            continue
        if entry.is_dir():
            continue
        if name in seen:
            raise ValueError(f"Duplicate JAR entry: {name!r}")
        seen.add(name)
        files.append(name)
    return sorted(files)


def _metadata_key(name: str, kind: str) -> str | None:
    if kind == "jar":
        return name if name in METADATA else None
    for key in METADATA:
        if name == key or name.endswith(f"/resources/{key}"):
            return key
    return None


def _source_set(name: str, folders: set[str]) -> str | None:
    parts = name.split("/")
    for index, part in enumerate(parts[:-3]):
        if part == "src" and parts[index + 2] in folders:
            return "/".join(parts[: index + 3])
    return None


def _as_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, list):
        return (entry for entry in value if isinstance(entry, dict))
    return ()


def _exact(value: Any, dialect: str) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if dialect == "forge" and value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    elif value.startswith("="):
        value = value[1:]
    elif dialect in {"forge", "quilt"}:
        return None
    return value if EXACT_RELEASE.fullmatch(value) else None


class Inventory:
    """Collect observations, then reconcile equally strong candidates."""

    def __init__(self, kind: str, warnings: list[str]) -> None:
        self.kind = kind
        self.warnings = warnings
        self.fields: dict[str, list[tuple[str, str, str]]] = {
            field: [] for field in ("minecraft", "loader", "java", "build", "mappings")
        }
        self.mod_ids: set[str] = set()
        self.dependencies: list[dict[str, Any]] = []
        self._dependency_keys: set[tuple[str, str, str, str]] = set()
        self.subsystems: dict[str, set[str]] = defaultdict(set)
        self.properties: dict[str, dict[str, str]] = {}

    def observe(
        self, field: str, value: str, evidence: str, *, confirmed: bool = True
    ) -> None:
        confidence = "confirmed" if confirmed else "heuristic"
        self.fields[field].append((value, confidence, evidence))

    def properties_for(self, name: str) -> dict[str, str]:
        combined: dict[str, str] = {}
        for parent in reversed(PurePosixPath(name).parents):
            combined.update(self.properties.get(parent.as_posix(), {}))
        return combined

    def substitute(self, value: Any, name: str) -> Any:
        if not isinstance(value, str):
            return value
        properties = self.properties_for(name)
        return PROPERTY_REFERENCE.sub(
            lambda item: properties.get(item[1].removeprefix("project."), item[0]),
            value,
        )

    def add_id(self, value: Any, name: str) -> None:
        value = self.substitute(value, name)
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.-]+", value):
            self.mod_ids.add(value)

    def dependency(
        self,
        identifier: Any,
        requirement: Any,
        category: str,
        name: str,
        dialect: str,
    ) -> None:
        if not isinstance(identifier, str) or not identifier:
            return
        if dialect == "forge" and not isinstance(requirement, str):
            self.warnings.append(
                f"Ignored non-string versionRange for {identifier} in {name}"
            )
            return
        resolved = self.substitute(requirement, name)
        key = (identifier, repr(resolved), category, name)
        entry = {
            "id": identifier,
            "requirement": resolved,
            "kind": category,
            "evidence": name,
        }
        if key not in self._dependency_keys:
            self._dependency_keys.add(key)
            self.dependencies.append(entry)
        if ":" in identifier and not identifier.startswith(
            (
                "com.mojang:",
                "net.minecraft:",
                "net.fabricmc:",
                "net.minecraftforge:",
                "net.neoforged:",
                "org.quiltmc:",
            )
        ):
            self.feature("integrations", name)
        if category != "required":
            return
        if identifier == "minecraft" and (version := _exact(resolved, dialect)):
            self.observe("minecraft", version, f"{name}: required Minecraft {resolved}")
        if identifier == "java" and isinstance(resolved, str):
            match = re.fullmatch(r"(?:>=|=)?([0-9]+)", resolved)
            if match:
                self.observe(
                    "java",
                    match[1],
                    f"{name}: declared Java requirement {resolved}",
                    confirmed=not resolved.startswith(">="),
                )

    def feature(self, key: str, name: str) -> None:
        self.subsystems[key].add(name)

    def read_metadata(self, key: str, name: str, content: str) -> None:
        try:
            payload = (
                tomllib.loads(content) if key.endswith(".toml") else json_load(content)
            )
            if not isinstance(payload, dict) and not (
                key == "mcmod.info" and isinstance(payload, list)
            ):
                raise ValueError("unexpected metadata root type")
            if key == "fabric.mod.json":
                self.fabric(payload, name)
            elif key == "quilt.mod.json":
                self.quilt(payload, name)
            elif key == "mcmod.info":
                self.legacy(payload, name)
            else:
                self.forge(payload, key, name)
        except (ValueError, RecursionError) as exc:
            self.warnings.append(f"Invalid metadata in {name}: {exc}")

    def fabric(self, data: dict[str, Any], name: str) -> None:
        if not isinstance(data.get("id"), str):
            raise ValueError("missing Fabric mod id")
        self.observe("loader", "fabric", name)
        self.add_id(data.get("id"), name)
        for field, category in (
            ("depends", "required"),
            ("recommends", "recommended"),
            ("suggests", "optional"),
            ("breaks", "incompatible"),
            ("conflicts", "conflicts"),
        ):
            if isinstance(data.get(field), dict):
                for identifier, requirement in data[field].items():
                    self.dependency(identifier, requirement, category, name, "fabric")
        for field, subsystem in (
            ("mixins", "mixins"),
            ("accessWidener", "access-wideners"),
            ("entrypoints", "initialization"),
            ("jars", "integrations"),
        ):
            if data.get(field):
                self.feature(subsystem, name)

    def quilt(self, data: dict[str, Any], name: str) -> None:
        loader = data.get("quilt_loader")
        if not isinstance(loader, dict):
            raise ValueError("missing quilt_loader object")
        self.observe("loader", "quilt", name)
        self.add_id(loader.get("id"), name)
        for field, category in (("depends", "required"), ("breaks", "incompatible")):
            entries = loader.get(field)
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, str):
                        self.dependency(entry, "*", category, name, "quilt")
                    elif isinstance(entry, dict):
                        entry_category = (
                            "optional" if entry.get("optional") else category
                        )
                        self.dependency(
                            entry.get("id"),
                            entry.get("versions", "*"),
                            entry_category,
                            name,
                            "quilt",
                        )
                    elif isinstance(entry, list):
                        self.warnings.append(
                            f"Grouped Quilt dependency requires manual review: {name}"
                        )
        if (
            self.kind == "jar"
            and loader.get("intermediate_mappings") == "net.fabricmc:intermediary"
        ):
            self.observe("mappings", "intermediary", name, confirmed=False)
        for field, subsystem in (
            ("mixin", "mixins"),
            ("access_widener", "access-wideners"),
        ):
            if data.get(field):
                self.feature(subsystem, name)
        if loader.get("entrypoints"):
            self.feature("initialization", name)

    def forge(self, data: dict[str, Any], key: str, name: str) -> None:
        loader = METADATA[key]
        table = data.get("dependencies")
        entries = (
            [item for group in table.values() for item in _as_objects(group)]
            if isinstance(table, dict)
            else []
        )
        loader_deps = {
            item.get("modId") for item in entries if isinstance(item.get("modId"), str)
        }
        if key == "META-INF/mods.toml":
            if "neoforge" in loader_deps:
                loader = "neoforge"
            # Older NeoForge versions also used mods.toml.
            self.observe(
                "loader",
                loader,
                name,
                confirmed=bool(loader_deps & {"forge", "neoforge"}),
            )
        else:
            self.observe("loader", loader, name)
        for entry in _as_objects(data.get("mods")):
            self.add_id(entry.get("modId"), name)
        for entry in entries:
            category = entry.get("type") or (
                "optional" if entry.get("mandatory") is False else "required"
            )
            if isinstance(category, str):
                self.dependency(
                    entry.get("modId"),
                    entry.get("versionRange", "*"),
                    category,
                    name,
                    "forge",
                )
        for field, subsystem in (
            ("mixins", "mixins"),
            ("accessTransformers", "access-transformers"),
        ):
            if data.get(field):
                self.feature(subsystem, name)

    def legacy(self, data: Any, name: str) -> None:
        self.observe("loader", "forge", name)
        if isinstance(data, dict):
            data = data.get("modList", [data])
        for entry in _as_objects(data):
            self.add_id(entry.get("modid"), name)
            version = entry.get("mcversion")
            if isinstance(version, str) and EXACT_RELEASE.fullmatch(version):
                self.observe("minecraft", version, f"{name}: mcversion")
            for field in ("requiredMods", "dependencies", "dependants"):
                if isinstance(entry.get(field), list):
                    for value in entry[field]:
                        if isinstance(value, str):
                            identifier, _, requirement = value.partition("@")
                            self.dependency(
                                identifier, requirement or "*", field, name, "legacy"
                            )

    def read_properties(self, name: str, content: str) -> None:
        properties = dict(
            re.findall(r"^\s*([\w.-]+)\s*[=:][ \t]*([^\r\n]*)", content, re.MULTILINE)
        )
        properties = {key: value.strip() for key, value in properties.items()}
        self.properties[PurePosixPath(name).parent.as_posix()] = properties
        for key in ("minecraft_version", "minecraftVersion", "mc_version"):
            version = properties.get(key, "")
            if EXACT_RELEASE.fullmatch(version):
                self.observe("minecraft", version, f"{name}: {key}")
        for key in ("java_version", "javaVersion"):
            version = properties.get(key, "")
            if re.fullmatch(r"[0-9]+", version):
                self.observe("java", version, f"{name}: {key}", confirmed=False)

    def gradle(self, name: str, content: str) -> None:
        self.observe("build", "gradle", name)
        # Read literal declarations and hints without evaluating Gradle.
        content = content.replace("\r\n", "\n")
        content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
        content = re.sub(r"(?m)^\s*//.*$", "", content)
        for marker, loader in (
            ("fabric-loom", "fabric"),
            ("net.minecraftforge.gradle", "forge"),
            ("net.neoforged.gradle", "neoforge"),
            ("net.neoforged.moddev", "neoforge"),
            ("org.quiltmc.loom", "quilt"),
        ):
            if marker in content:
                self.observe("loader", loader, f"{name}: {marker}", confirmed=False)
        direct_mojang = re.search(
            r"(?m)^[ \t]*mappings(?:[ \t]+|[ \t]*\([ \t]*)"
            r"loom\.officialMojangMappings\(\s*\)[ \t]*\)?[ \t]*;?[ \t]*(?://[^\n]*)?$",
            content,
        )
        for namespace, pattern in {
            "mojang": r"\bofficialMojangMappings\s*\(|\bmappings\b[^\n]+(?:channel\s*[=:]\s*['\"]official|['\"]official['\"])",
            "yarn": r"\bnet\.fabricmc:yarn:",
            "intermediary": r"\bnet\.fabricmc:intermediary:",
            "quilt": r"\borg\.quiltmc:quilt-mappings:",
            "mcp": r"\b(?:de\.oceanlabs\.mcp:|mappings\b[^\n]+['\"](?:snapshot|stable)(?:_|['\"]))",
            "srg": r"\bmappings\b[^\n]+['\"](?:srg|tsrg)['\"]",
        }.items():
            if re.search(pattern, content):
                self.observe(
                    "mappings",
                    namespace,
                    f"{name}: {namespace} mapping declaration",
                    confirmed=namespace == "mojang" and direct_mojang is not None,
                )
        java_pattern = (
            r"\blanguageVersion\s*(?:=\s*|\.set\(\s*)JavaLanguageVersion\.of\(\s*([0-9]+)\s*\)"
            r"|(?:sourceCompatibility|targetCompatibility|options\.release)\s*(?:[.=]\s*(?:set\s*\(\s*)?)?"
            r"(?:JavaVersion\.VERSION_)?['\"]?(?:1[._])?([0-9]+)"
        )
        for match in re.finditer(java_pattern, content):
            self.observe(
                "java",
                match[1] or match[2],
                f"{name}: {match[0].strip()}",
                confirmed=match[1] is not None,
            )
        for match in GRADLE_DEPENDENCY.finditer(content):
            configuration, coordinate = match.groups()
            group, artifact, *versions = coordinate.split(":")
            version = self.substitute(versions[0], name) if versions else "*"
            self.dependency(
                f"{group}:{artifact}", version, configuration, name, "gradle"
            )
            if (
                group in {"net.minecraft", "com.mojang"}
                and artifact == "minecraft"
                and EXACT_RELEASE.fullmatch(version)
            ):
                self.observe(
                    "minecraft", version, f"{name}: {coordinate}", confirmed=False
                )
            if group == "net.minecraftforge" and artifact == "forge":
                minecraft = version.partition("-")[0]
                if EXACT_RELEASE.fullmatch(minecraft):
                    self.observe(
                        "minecraft", minecraft, f"{name}: {coordinate}", confirmed=False
                    )
        for subsystem in ("access-transformers", "access-wideners"):
            if re.search(SUBSYSTEMS[subsystem], content):
                self.feature(subsystem, name)

    def catalog(self, name: str, content: str) -> None:
        try:
            document = tomllib.loads(content)
        except (ValueError, RecursionError) as exc:
            self.warnings.append(f"Invalid version catalog in {name}: {exc}")
            return
        versions = document.get("versions")
        if not isinstance(versions, dict):
            return
        version = versions.get("minecraft")
        if isinstance(version, str) and EXACT_RELEASE.fullmatch(version):
            self.observe(
                "minecraft", version, f"{name}: versions.minecraft", confirmed=False
            )

    def maven(self, name: str, content: str) -> None:
        self.observe("build", "maven", name)
        if "<!DOCTYPE" in content:
            self.warnings.append(
                f"Skipped Maven XML with a document type declaration: {name}"
            )
            return
        try:
            document = ElementTree.fromstring(content)
        except ElementTree.ParseError as exc:
            self.warnings.append(f"Invalid Maven XML in {name}: {exc}")
            return
        for node in document.findall("./{*}dependencies/{*}dependency"):
            group = node.findtext("{*}groupId")
            artifact = node.findtext("{*}artifactId")
            if group and artifact:
                self.dependency(
                    f"{group}:{artifact}",
                    node.findtext("{*}version", "*"),
                    node.findtext("{*}scope", "compile"),
                    name,
                    "maven",
                )
        for field in (
            "maven.compiler.release",
            "maven.compiler.target",
            "maven.compiler.source",
        ):
            version = document.findtext(f"./{{*}}properties/{{*}}{field}")
            if version and re.fullmatch(r"(?:1\.)?[0-9]+", version):
                self.observe(
                    "java",
                    version.removeprefix("1."),
                    f"{name}: {field}",
                    confirmed=False,
                )

    def environment(self) -> dict[str, dict[str, Any]]:
        environment = {}
        for field, candidates in self.fields.items():
            confirmed = [
                (value, evidence)
                for value, level, evidence in candidates
                if level == "confirmed"
            ]
            strongest = confirmed or [
                (value, evidence) for value, _, evidence in candidates
            ]
            values = sorted({value for value, _ in strongest})
            evidence = sorted({evidence for _, evidence in strongest})
            if len(values) > 1:
                self.warnings.append(
                    f"Conflicting {field} observations: {', '.join(values)}"
                )
            if len(values) == 1:
                weaker = sorted({value for value, _, _ in candidates} - set(values))
                if weaker:
                    self.warnings.append(
                        f"Other {field} hints require review: {', '.join(weaker)}"
                    )
                confidence = "confirmed" if confirmed else "heuristic"
                environment[field] = {
                    "value": values[0],
                    "confidence": confidence,
                    "evidence": evidence,
                }
            else:
                environment[field] = {
                    "value": None,
                    "confidence": "unknown",
                    "evidence": evidence,
                }
        return environment


def _analyze(
    root: Path,
    kind: str,
    files: list[str],
    read: Callable[[str, int], bytes],
    warnings: list[str],
) -> dict[str, Any]:
    inventory = Inventory(kind, warnings)
    texts: dict[str, str] = {}
    source_dirs = set()
    resource_dirs = set()
    resources = []
    metadata = {}
    total = 0
    classes = []
    for name in files:
        path = PurePosixPath(name)
        if kind == "directory":
            if source_dir := _source_set(name, {"java", "kotlin", "scala"}):
                source_dirs.add(source_dir)
            if resource_dir := _source_set(name, {"resources"}):
                resource_dirs.add(resource_dir)
                resources.append(name)
        if kind == "jar":
            if name.startswith(("assets/", "data/")):
                resources.append(name)
                resource_dirs.add(path.parts[0])
            if path.suffix == ".class" and not name.startswith("META-INF/versions/"):
                classes.append(name)
        if key := _metadata_key(name, kind):
            metadata[name] = key
        if re.search(r"(?:^|/)assets/", name):
            inventory.feature("resources", name)
        if re.search(r"(?:^|/)data/", name):
            inventory.feature("data-packs", name)
        if re.search(r"(?:^|/)(?:[^/]*mixins?[^/]*\.json)$", name):
            inventory.feature("mixins", name)
        if path.suffix == ".accesswidener":
            inventory.feature("access-wideners", name)
        if path.name.endswith("_at.cfg"):
            inventory.feature("access-transformers", name)
        if name.endswith("META-INF/coremods.json"):
            inventory.feature("access-transformers", name)
        if kind == "directory" and not (
            key or path.name in BUILD_FILES or path.suffix in SOURCE_SUFFIXES
        ):
            continue
        if kind == "jar" and not (key or name == "META-INF/MANIFEST.MF"):
            continue
        if total >= MAX_TOTAL_BYTES:
            continue
        limit = min(MAX_TEXT_BYTES, MAX_TOTAL_BYTES - total)
        try:
            data = read(name, limit + 1)
            total += len(data)
            if len(data) > limit:
                warnings.append(f"Skipped oversized text file: {name}")
            else:
                texts[name] = data.decode("utf-8-sig")
        except (
            OSError,
            ValueError,
            RuntimeError,
            zipfile.BadZipFile,
            zlib.error,
        ) as exc:
            warnings.append(f"Could not read {name}: {exc}")
    if total >= MAX_TOTAL_BYTES:
        warnings.append(
            "Text inspection reached the byte budget. Inventory may be incomplete."
        )
    for name, content in texts.items():
        if PurePosixPath(name).name == "gradle.properties":
            inventory.read_properties(name, content)
    for name, content in texts.items():
        path = PurePosixPath(name)
        if name in metadata:
            inventory.read_metadata(metadata[name], name, content)
        elif kind == "directory" and path.name in BUILD_FILES:
            if path.name.endswith((".gradle", ".gradle.kts")):
                inventory.gradle(name, content)
            elif path.name == "pom.xml":
                inventory.maven(name, content)
            elif path.name == "libs.versions.toml":
                inventory.catalog(name, content)
        elif kind == "directory" and path.suffix in SOURCE_SUFFIXES:
            for subsystem, pattern in SUBSYSTEMS.items():
                if re.search(pattern, content):
                    inventory.feature(subsystem, name)
        elif name == "META-INF/MANIFEST.MF":
            if re.search(r"(?im)^MixinConfigs:\s*\S+", content):
                inventory.feature("mixins", name)
            if re.search(r"(?im)^(?:FMLAT|FMLCorePlugin):\s*\S+", content):
                inventory.feature("access-transformers", name)
    if classes:
        majors = set()
        for name in classes[:1000]:
            try:
                header = read(name, 8)
            except (
                OSError,
                ValueError,
                RuntimeError,
                zipfile.BadZipFile,
                zlib.error,
            ) as exc:
                warnings.append(f"Could not read class header {name}: {exc}")
                continue
            if len(header) == 8 and header[:4] == b"\xca\xfe\xba\xbe":
                major = int.from_bytes(header[6:8], "big")
                if 45 <= major <= 255:
                    majors.add(major)
        if majors:
            inventory.observe(
                "java",
                str(max(majors) - 44),
                "highest sampled base class-file major version",
                confirmed=False,
            )
        if len(classes) > 1000:
            warnings.append(
                "Class-file inspection sampled the first 1,000 base classes."
            )
    environment = inventory.environment()
    if not metadata:
        warnings.append(
            "No supported mod metadata file found in conventional locations."
        )
    return {
        "schema_version": 1,
        "source": str(root),
        "kind": kind,
        "environment": environment,
        "mod_ids": sorted(inventory.mod_ids),
        "dependencies": inventory.dependencies,
        "source_directories": sorted(source_dirs),
        "resource_directories": sorted(resource_dirs),
        "subsystems": {
            key: sorted(entries)
            for key, entries in sorted(inventory.subsystems.items())
        },
        "metadata_files": sorted(metadata),
        "resources": sorted(resources),
        "warnings": warnings,
    }


def scan(path: Path) -> dict[str, Any]:
    """Inspect project declarations and static signals without executing build files or JARs."""
    root = safe_path(path)
    warnings: list[str] = []
    if root.is_dir():
        files = _directory_files(root, warnings)

        def read(name: str, size: int) -> bytes:
            candidate = safe_path(root / name)
            if not stat.S_ISREG(candidate.lstat().st_mode):
                raise OSError(f"Path changed to a non-regular file: {name}")
            with candidate.open("rb") as stream:
                return stream.read(size)

        return _analyze(root, "directory", files, read, warnings)
    if not root.is_file() or root.suffix.lower() != ".jar":
        raise ValueError("Expected a source directory or .jar file")
    if root.stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError("JAR exceeds the 256 MiB archive limit")
    _check_archive_index(root)
    try:
        with zipfile.ZipFile(root) as archive:
            files = _archive_files(archive, warnings)

            def read_archive(name: str, size: int) -> bytes:
                entry = archive.getinfo(name)
                if entry.compress_type not in {
                    zipfile.ZIP_STORED,
                    zipfile.ZIP_DEFLATED,
                }:
                    raise ValueError("Unsupported JAR compression method")
                with archive.open(entry) as stream:
                    return stream.read(size)

            return _analyze(root, "jar", files, read_archive, warnings)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Invalid JAR archive: {exc}") from exc
