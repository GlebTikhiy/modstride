# Architecture and initial scope

The CLI coordinates static inventory, capability assessment, validated rules, isolated execution and evidence reporting. JSON contracts carry scan, plan and workspace state. The Python CLI works offline with the standard library. Engine profiles describe capabilities and Java target metadata. A rule catalogue ships as package data so installed and development invocations use the same inputs.

## ADR 001 · Start with a narrow reproducible migration

Reviewed 2026-11-13.

[universal-modder](https://github.com/rehan-remade/universal-modder) bundles Claude-oriented game reconnaissance, modding, testing and creative tooling. [mc-mod-version-upgrade](https://github.com/jivinstev/mc-mod-version-upgrade) couples focused porting skills with Java transformations and real-game verification gates. Both demonstrate the value of evidence and isolation. modstride adopts those patterns in an independent implementation with an Agent Skills-compatible package, versioned plan and evidence contracts, an offline scanner and a data-only rule extension point. It starts with a Fabric configuration transition. Java API porting, build validation and gameplay verification have separate criteria.

The first target is Fabric 1.20.4 from Fabric 1.20.1, using Java 17 and Mojang mappings in the original sample. The rules retarget a literal Gradle property and an exact Fabric metadata dependency. Loader source and Maven publication document the metadata and pinned tools. Java analysis is heuristic and hands semantic changes to an agent with upstream source evidence.

- [Agent Skills format](https://agentskills.io/specification)
- [Fabric Loader 0.15.11 metadata parser](https://github.com/FabricMC/fabric-loader/blob/0.15.11/src/main/java/net/fabricmc/loader/impl/metadata/V1ModMetadataParser.java)
- [Fabric Loom 1.6.12 publication](https://maven.fabricmc.net/net/fabricmc/fabric-loom/1.6.12/)
- [Gradle Java compatibility](https://docs.gradle.org/current/userguide/compatibility.html)
- [Fabric porting documentation](https://docs.fabricmc.net/develop/porting/)
- [Forge 1.20.1 documentation](https://docs.minecraftforge.net/en/1.20.1/)
- [NeoForge 1.21.1 documentation](https://docs.neoforged.net/docs/1.21.1/)
- [Fabric Intermediary](https://github.com/FabricMC/intermediary) and [Tiny Remapper](https://github.com/FabricMC/tiny-remapper)
- [Horizon mod architecture](https://github.com/horizon-rust/horizon/blob/main/docs/mods.md) and [API design](https://github.com/horizon-rust/horizon/blob/main/docs/api/README.md)

A general Java AST rewrite engine would need parser and cross-version symbol resolution before it could safely transform production code. Configuration-only rules have smaller, testable preconditions. The Horizon adapter reports research requirements and compatibility assessment without binding to an unverified SDK release. Revisit these choices when multiple working examples need the same semantic transformation or a pinned engine SDK is available.
