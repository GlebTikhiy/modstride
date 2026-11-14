# Supported targets

| Source and target | Release capability | Evidence |
| --- | --- | --- |
| Fabric 1.20.1 → Fabric 1.20.4, Mojang mappings | Plan, two guarded configuration edits, static verification and optional Gradle build | Original Copper Token source and migrated builds passed. Runtime and parity checks pending. |
| Fabric 1.20.4 → Fabric 1.20.6, Mojang mappings | Demonstrated Java API migration for the Field Counter helper and guarded configuration edits | Builds and paired behavior probes. See the [0.2.0 evidence](development-0.2.0.md) for startup status and coverage. |
| Forge 1.12.2 → NeoForge 1.21.1 | Experimental assessment | Version-specific API research and subsystem porting guidance. Automatic conversion is unsupported. [Feasibility study](forge-1122-neoforge-1211.md) |
| Other Fabric versions | Static inventory and assisted planning | Review dependency pins, mappings and target Java APIs per project. |
| Forge, NeoForge and cross-loader combinations | Static inventory and assisted planning | Inspect replacement APIs and subsystem parity. No built-in code rewrites. |
| Quilt | Static inventory and assessment | Conventional metadata and heuristic source analysis. |
| Unknown Minecraft releases | Assessment | The toolchain stays unspecified until it has evidence. |
| Java Minecraft → Horizon | Experimental assessment | The profile classifies resources, initialization, world, scheduling, networking, rendering and persistence. No build integration or Rust code generation. |
| JAR → any target | Static inventory and assessment | No class execution, extraction or decompilation. |

The profile includes Java major-version starting points for Minecraft 1.7.10, 1.12.2, 1.16.5, 1.20.1, 1.20.4, 1.20.6 and 1.21.1. Check each loader, Gradle runtime and build plugin separately. A version in the profile is planning data and carries no automatic port guarantee.

The scanner recognizes declared Mojang mappings, Yarn, Intermediary, MCP, SRG and Quilt namespaces where detectable. `mappings lookup` accepts user-supplied Tiny v2.0 class and member names. Specify the owner's JVM internal name in the requested namespace. Member lookup also requires the descriptor from the table's first namespace. Use the exact table for the Minecraft and mapping release. Tiny escape-mode files, format conversion, and source and JAR remapping need an external tool. [Mapping migration](../skills/modstride/references/mapping-migration.md)

Horizon classifications describe modstride's current integration and expected porting effort. Confirm capabilities against a pinned Horizon release before a reimplementation. [Horizon upstream documentation](https://github.com/horizon-rust/horizon/blob/main/docs/mods.md)
