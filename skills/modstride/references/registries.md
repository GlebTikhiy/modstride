# Registries

Inventory keys and registration timing for blocks and their items, entity and block entity types, serializers, menus and worldgen. Keep namespaced IDs stable where feasible because saves, commands, loot tables and other mods reference them. Check aliases and remapping hooks before changing any IDs.

Forge 1.12.x provides registry events such as `RegistryEvent.Register`. NeoForge 1.21.1 supports `DeferredRegister` on the mod event bus and explicit `RegisterEvent` listeners. Initialize objects at the required stage and verify when holders resolve. Data-driven registries need checks against the target's data-loading lifecycle. [Forge 1.12 registries](https://docs.minecraftforge.net/en/1.12.x/concepts/registries/) · [NeoForge 1.21.1 registries](https://docs.neoforged.net/docs/1.21.1/concepts/registries/)

Check registered keys on a fresh server. Open a disposable old save and verify blocks, stacks, custom entities and dimensions resolve. Check data-pack reload for dynamic entries.
