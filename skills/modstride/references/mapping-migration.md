# Mapping migration

Treat game version and namespace as independent coordinates. Record exact mapping artifacts, licenses and the namespace of the published mod. Yarn and Mojang mappings provide readable names. Intermediary provides names used in compiled Fabric mods on obfuscated versions. Legacy Forge builds can use MCP development names and SRG for production. Inspect the build to establish the actual namespace. [Fabric mapping migration](https://docs.fabricmc.net/develop/porting/mappings/) · [ForgeGradle mappings](https://docs.minecraftforge.net/en/fg-6.x/configuration/)

Use a compatible Loom `migrateMappings` task for Java source after checking the pinned version's supported options. Inspect the output before incorporating it. Tiny Remapper remaps JARs. Audit mixin string targets, access rules, reflection, generated resources and other dynamic references independently. [Fabric Loom](https://docs.fabricmc.net/develop/loom/) · [Tiny Remapper](https://github.com/FabricMC/tiny-remapper)

Resolve ambiguous members by owner, name and JVM descriptor in the exact artifacts. Verify semantics in the target call sites. Record absent or ambiguous mappings as unresolved and respect redistribution terms. [Yarn](https://github.com/FabricMC/yarn) · [Intermediary](https://github.com/FabricMC/intermediary)

For a local Tiny v2.0 table, run `modstride mappings lookup TABLE --namespace NAMESPACE --owner JVM_CLASS`. Use the slash-separated class name in the selected namespace. For a member, add `--member NAME --descriptor DESCRIPTOR` and use the descriptor from the first namespace in the table header. [Tiny v2 specification](https://wiki.fabricmc.net/documentation:tiny2)
