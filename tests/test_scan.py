from __future__ import annotations

import json
import os
import stat
import zipfile
from pathlib import Path

import pytest

from modstride.scan import scan


def write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_fabric_source_inventory(tmp_path):
    root = tmp_path / "mod source with spaces"
    write(
        root, "gradle.properties", "minecraft_version=1.20.1\nloader_version=0.15.11\n"
    )
    write(
        root,
        "build.gradle.kts",
        """
        // mappings("net.fabricmc:intermediary:1.20.1")
        minecraft("com.mojang:minecraft:${project.minecraft_version}")
        modImplementation("net.fabricmc:fabric-loader:${loader_version}")
        mappings("net.fabricmc:yarn:1.20.1+build.10:v2")
        java.toolchain.languageVersion.set(JavaLanguageVersion.of(17))
        """,
    )
    metadata = {
        "schemaVersion": 1,
        "id": "test_mod",
        "depends": {
            "minecraft": ">=1.20 <1.21",
            "fabricloader": ">=0.15",
            "java": ">=17",
        },
        "mixins": [{"config": "testmod.mixins.json"}],
        "accessWidener": "testmod.accesswidener",
    }
    write(root, "src/main/resources/fabric.mod.json", json.dumps(metadata))
    write(root, "src/main/resources/assets/test_mod/lang/en_us.json", "{}")
    write(root, "src/main/resources/data/test_mod/recipes/copper_token.json", "{}")
    write(root, "src/client/kotlin/mod/Test.kt", "class Test : ClientModInitializer")
    write(
        root,
        "src/main/java/mod/Test.java",
        """
        Registry.register(x);
        @SubscribeEvent
        ServerPlayNetworking.send(x);
        ForgeConfigSpec config;
        SavedData data;
        EntityRenderer renderer;
        """,
    )
    write(root, "build/classes/fabric.mod.json", '{"id": "stale"}')
    report = scan(root)
    assert report["source"] == os.path.abspath(root)
    assert report["kind"] == "directory"
    assert report["mod_ids"] == ["test_mod"]
    fields = report["environment"]
    assert fields["minecraft"]["value"] == "1.20.1"
    assert fields["minecraft"]["confidence"] == "confirmed"
    assert fields["loader"]["value"] == "fabric"
    assert fields["loader"]["confidence"] == "confirmed"
    assert fields["java"]["value"] == "17"
    assert fields["java"]["confidence"] == "confirmed"
    assert fields["mappings"]["value"] == "yarn"
    assert fields["build"]["value"] == "gradle"
    assert report["source_directories"] == ["src/client/kotlin", "src/main/java"]
    assert report["resource_directories"] == ["src/main/resources"]
    assert len(report["resources"]) == 3
    assert {
        "initialization",
        "registries",
        "events",
        "networking",
        "configuration",
        "persistence",
        "rendering",
        "resources",
        "data-packs",
        "mixins",
        "access-wideners",
    } <= report["subsystems"].keys()
    requirements = {item["id"]: item["requirement"] for item in report["dependencies"]}
    assert requirements["minecraft"] == ">=1.20 <1.21"
    assert requirements["com.mojang:minecraft"] == "1.20.1"
    assert requirements["net.fabricmc:fabric-loader"] == "0.15.11"


@pytest.mark.parametrize(
    ("metadata_file", "metadata", "loader", "version"),
    [
        (
            "META-INF/mods.toml",
            """
            modLoader = "javafml"
            [[mods]]
            modId = "${mod_id}"
            [[dependencies.mod]]
            modId = "forge"
            mandatory = true
            versionRange = "[47,)"
            [[dependencies.mod]]
            modId = "minecraft"
            versionRange = "[1.20.1]"
            """,
            "forge",
            "1.20.1",
        ),
        (
            "META-INF/neoforge.mods.toml",
            """
            modLoader = "javafml"
            [[mods]]
            modId = "test_mod"
            [[dependencies.test_mod]]
            modId = "minecraft"
            type = "required"
            versionRange = "[1.21.1,1.22)"
            """,
            "neoforge",
            None,
        ),
        (
            "quilt.mod.json",
            '{"schema_version": 1, "quilt_loader": {"id": "test_mod", "depends": '
            '[{"id": "minecraft", "versions": "=1.19.2"}, "qsl"]}, "mixin": "example.mixins.json"}',
            "quilt",
            "1.19.2",
        ),
        (
            "mcmod.info",
            '{"modList": [{"modid": "test_mod", "mcversion": "1.12.2", "dependencies": ["a@1.0"]}]}',
            "forge",
            "1.12.2",
        ),
    ],
)
def test_loader_metadata(tmp_path, metadata_file, metadata, loader, version):
    write(tmp_path, "gradle.properties", "mod_id=test_mod\n")
    write(tmp_path, f"src/main/resources/{metadata_file}", metadata)
    report = scan(tmp_path)
    assert report["mod_ids"] == ["test_mod"]
    assert report["environment"]["loader"]["value"] == loader
    assert report["environment"]["loader"]["confidence"] == "confirmed"
    assert report["environment"]["minecraft"]["value"] == version
    assert report["environment"]["mappings"]["confidence"] == "unknown"


def test_gradle_legacy_mcp_and_build_java(tmp_path):
    write(
        tmp_path,
        "build.gradle",
        """
        apply plugin: 'net.minecraftforge.gradle.forge'
        sourceCompatibility = targetCompatibility = JavaVersion.VERSION_1_8
        minecraft {
            mappings = 'snapshot_20171003'
        }
        minecraft 'net.minecraftforge:forge:1.12.2-14.23.5.2859'
        """,
    )
    fields = scan(tmp_path)["environment"]
    assert fields["loader"]["value"] == "forge"
    assert fields["loader"]["confidence"] == "heuristic"
    assert fields["minecraft"]["value"] == "1.12.2"
    assert fields["mappings"]["value"] == "mcp"
    assert fields["java"]["value"] == "8"


def test_conflicting_exact_versions_remain_ambiguous(tmp_path):
    write(tmp_path, "gradle.properties", "minecraft_version=1.20.1\n")
    write(
        tmp_path,
        "src/main/resources/fabric.mod.json",
        '{"id":"mod","depends":{"minecraft":"1.20.4"}}',
    )
    report = scan(tmp_path)
    assert report["environment"]["minecraft"]["value"] is None
    assert any("Conflicting minecraft" in warning for warning in report["warnings"])


@pytest.mark.parametrize(
    ("declaration", "confidence"),
    [
        ("mappings loom.officialMojangMappings()", "confirmed"),
        ("mappings(loom.officialMojangMappings())", "confirmed"),
        ("def layers = loom.officialMojangMappings()", "heuristic"),
    ],
)
def test_direct_mojang_mapping_declaration(tmp_path, declaration, confidence):
    write(tmp_path, "build.gradle", declaration + "\n")
    field = scan(tmp_path)["environment"]["mappings"]
    assert field["value"] == "mojang"
    assert field["confidence"] == confidence


def test_invalid_and_duplicate_json_metadata_is_warning(tmp_path):
    write(tmp_path, "src/main/resources/fabric.mod.json", '{"id":"mod","id":"other"}')
    report = scan(tmp_path)
    assert report["mod_ids"] == []
    assert report["environment"]["loader"]["confidence"] == "unknown"
    assert any("Duplicate JSON key" in warning for warning in report["warnings"])


def test_inventory_keeps_source_paths_with_common_generated_directory_names(tmp_path):
    write(
        tmp_path,
        "src/main/java/mod/world/Weather.java",
        "class Weather extends SavedData {}",
    )
    write(tmp_path, "src/main/resources/assets/build/lang/en_us.json", "{}")
    write(tmp_path, "custom-saves/example/level.dat", "")
    write(
        tmp_path,
        "custom-saves/example/src/main/resources/fabric.mod.json",
        '{"id":"save"}',
    )
    write(tmp_path, "Build/src/main/resources/fabric.mod.json", '{"id":"generated"}')
    report = scan(tmp_path)
    assert report["subsystems"]["persistence"] == [
        "src/main/java/mod/world/Weather.java"
    ]
    assert report["resources"] == ["src/main/resources/assets/build/lang/en_us.json"]
    assert report["mod_ids"] == []


def test_safe_static_jar_inventory(tmp_path):
    jar = tmp_path / "source mod.jar"
    with zipfile.ZipFile(jar, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "fabric.mod.json", '{"id": "jar_mod","depends":{"minecraft":"1.20.1"}}'
        )
        archive.writestr("pkg/Entrypoint.class", b"\xca\xfe\xba\xbe\0\0\0=")
        archive.writestr(
            "META-INF/versions/21/pkg/Entrypoint.class", b"\xca\xfe\xba\xbe\0\0\0A"
        )
        archive.writestr(
            "META-INF/MANIFEST.MF", "Manifest-Version: 1.0\nFMLAT: legacy.cfg\n"
        )
        archive.writestr("assets/jar_mod/lang/en_us.json", "{}")
        archive.writestr("../quilt.mod.json", '{"quilt_loader":{"id":"malicious"}}')
        link = zipfile.ZipInfo("quilt.mod.json")
        link.create_system = 3
        link.external_attr = stat.S_IFLNK << 16
        archive.writestr(link, "other")
    report = scan(jar)
    assert report["kind"] == "jar"
    assert report["mod_ids"] == ["jar_mod"]
    assert report["environment"]["java"]["value"] == "17"
    assert report["environment"]["java"]["confidence"] == "heuristic"
    assert report["environment"]["mappings"]["value"] is None
    assert report["source_directories"] == []
    assert report["resource_directories"] == ["assets"]
    assert report["subsystems"]["access-transformers"] == ["META-INF/MANIFEST.MF"]
    assert (
        sum("Skipped unsafe archive entry" in warning for warning in report["warnings"])
        == 2
    )
    assert not (tmp_path / "quilt.mod.json").exists()


def test_corrupt_jar(tmp_path):
    jar = tmp_path / "bad.jar"
    jar.write_bytes(b"This is not an archive.")
    with pytest.raises(ValueError, match="Invalid JAR archive"):
        scan(jar)


def test_duplicate_jar_entries_are_ambiguous(tmp_path):
    jar = tmp_path / "duplicate.jar"
    with zipfile.ZipFile(jar, "w") as archive:
        archive.writestr("fabric.mod.json", '{"id":"first"}')
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr("fabric.mod.json", '{"id":"second"}')
    with pytest.raises(ValueError, match="Duplicate JAR entry"):
        scan(jar)


def test_oversized_archive_metadata_skipped(tmp_path):
    jar = tmp_path / "large-metadata.jar"
    with zipfile.ZipFile(jar, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("fabric.mod.json", " " * (512 * 1024 + 1))
    report = scan(jar)
    assert report["environment"]["loader"]["value"] is None
    assert any("oversized text file" in warning for warning in report["warnings"])


def test_malformed_archive_index_is_rejected(tmp_path):
    jar = tmp_path / "large-index.jar"
    with zipfile.ZipFile(jar, "w") as archive:
        archive.writestr("fabric.mod.json", '{"id":"test_mod"}')
    data = bytearray(jar.read_bytes())
    data[-10:-6] = (256 * 1024 * 1024).to_bytes(4, "little")
    jar.write_bytes(data)
    with pytest.raises(ValueError, match="central directory exceeds"):
        scan(jar)


def test_directory_scan_does_not_traverse_link(tmp_path):
    outside = tmp_path / "other"
    write(outside, "main/resources/fabric.mod.json", '{"id":"outside"}')
    root = tmp_path / "mod"
    root.mkdir()
    try:
        (root / "src").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Windows developer mode or symlink privilege is unavailable")
    report = scan(root)
    assert report["mod_ids"] == []
    assert any("linked directory" in warning for warning in report["warnings"])
    with pytest.raises(ValueError, match="Symlink or reparse point"):
        scan(root / "src" / "main")


def test_maven_dependency_inventory_without_resolution(tmp_path):
    write(
        tmp_path,
        "pom.xml",
        """
        <project xmlns="http://maven.apache.org/POM/4.0.0">
          <properties><maven.compiler.release>21</maven.compiler.release></properties>
          <dependencies>
            <dependency>
              <groupId>org.example</groupId><artifactId>missing</artifactId><version>0.0</version>
            </dependency>
          </dependencies>
        </project>
        """,
    )
    report = scan(tmp_path)
    assert report["environment"]["java"]["value"] == "21"
    assert report["environment"]["build"]["value"] == "maven"
    assert report["dependencies"] == [
        {
            "id": "org.example:missing",
            "kind": "compile",
            "requirement": "0.0",
            "evidence": "pom.xml",
        }
    ]
