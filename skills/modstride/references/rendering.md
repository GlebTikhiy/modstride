# Rendering and menus

Keep client renderers, screens, key bindings and HUD classes on client-only paths. Verify dedicated server startup because class linkage can fail before a method's side guard runs. Keep menu state and interaction checks authoritative on the server. [NeoForge 1.21.1 sides](https://docs.neoforged.net/docs/1.21.1/concepts/sides/) · [NeoForge 1.21.1 menus](https://docs.neoforged.net/docs/1.21.1/gui/menus/)

Legacy tile-entity rendering and modern block-entity rendering use different registration, transforms and buffer lifecycles. Confirm the target registration hook, available state, shader or render-type choices and reload behavior. Keep mutable per-instance animation state with its owner. [NeoForge 1.21.1 block entity renderers](https://docs.neoforged.net/docs/1.21.1/blockentities/ber/)

Compare visual states, animation, lighting, missing assets, menu resize and out-of-range interactions. Start a dedicated server with the same common artifact and inspect for client class references.
