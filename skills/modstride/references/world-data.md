# World data and configuration

Map saved data, entity and block-entity NBT, item stacks, capabilities or attachments, configurations and registry keys. Record which data is per level, global, per player or per stack. Preserve key types, defaults and ownership. Design conversion for old and malformed values and verify a retry preserves already migrated data.

For NeoForge 1.21.1 compare level-wide `SavedData`, object attachments and custom item-stack data components. Inspect persistence and network codecs independently. Check dirty marking, entity synchronization and reload. [Saved data](https://docs.neoforged.net/docs/1.21.1/datastorage/saveddata/) · [Attachments](https://docs.neoforged.net/docs/1.21.1/datastorage/attachments/) · [Item data components](https://docs.neoforged.net/docs/1.21.1/items/datacomponents/)

Use a fresh world and a disposable copy of a closed backup. Exercise save/reopen, dimension travel, unload/reload, reconnect and rollback. Compare registry resolution, persistent values and player-facing effects. Document dropped information and how to restore the backup.
