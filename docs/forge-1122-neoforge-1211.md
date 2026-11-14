# Forge 1.12.2 → NeoForge 1.21.1 feasibility

This route is experimental planning. A port is feasible for mods whose dependencies and gameplay contracts can be reproduced, but feasibility varies with the source. This release ships no automatic edits for the route. The API references below support investigation and design. An actual legacy project and a built NeoForge counterpart are needed to verify a transformation.

| Area | Forge 1.12.2 | NeoForge 1.21.1 | Porting and verification |
| --- | --- | --- | --- |
| Entry point and lifecycle | `@Mod`, pre/init/post handlers and sided proxies | Mod constructor, lifecycle events and explicit physical sides | Inventory side effects and order, wire handlers to the right bus, check dedicated-server class loading. |
| Registries | `RegistryEvent.Register<T>`, `setRegistryName`, `ObjectHolder` | `DeferredRegister` and deferred holders, or `RegisterEvent` | Preserve registry IDs and create dependent objects at the correct stage. Verify lookup, block items, and registration order on a clean launch. |
| Networking | `SimpleNetworkWrapper`, numeric discriminators, explicit main-thread scheduling | Typed `CustomPacketPayload`, `StreamCodec`, `RegisterPayloadHandlersEvent` | Design a new protocol and check direction, authorization, thread policy and synchronization. Assume mixed-generation clients are incompatible. |
| Persistence | Legacy tile entity NBT, capabilities and block metadata | Block entities with registry-aware serialization, state properties, capabilities or attachments | Inventory IDs and codecs, then test backups and representative old saves. Preserving IDs alone gives no evidence that the data survives. |
| Resources and mappings | MCP-era names, legacy models, recipes and localization | Mojang names and modern data and resource packs | Use version-specific artifacts and inspect behavior at each call site. Port assets and data formats separately. |

Start with a small behavior slice. Capture one legacy item or block in a disposable 1.12.2 world. Compare registration, placement or use, save and reload, and dedicated-server behavior with a small modern implementation. Add an intermediate migration only where it isolates a specific blocker such as data conversion or an unavailable dependency. A full intermediate version ladder can compound API and tooling work.

The historical and target APIs were checked against their upstream documentation. No legacy project was compiled or launched for this assessment.

- [Forge 1.12 registries](https://docs.minecraftforge.net/en/1.12.x/concepts/registries/) · [Forge loading stages](https://docs.minecraftforge.net/en/1.12.x/conventions/loadstages/) · [Forge SimpleImpl](https://docs.minecraftforge.net/en/1.12.x/networking/simpleimpl/)
- [NeoForge 1.21.1 registries](https://docs.neoforged.net/docs/1.21.1/concepts/registries/) · [NeoForge events](https://docs.neoforged.net/docs/1.21.1/concepts/events/) · [NeoForge payloads](https://docs.neoforged.net/docs/1.21.1/networking/payload/) · [NeoForge block entities](https://docs.neoforged.net/docs/1.21.1/blockentities/)
