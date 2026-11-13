# Java to Rust engine assessment

Pin the engine release and SDK revision. Identify whether it supports a native build, runtime plugin, resource pack or another extension route. Check Horizon's API status and mod guide before selecting a route. A Java mod JAR depends on Java classes and cannot be used as a Horizon executable plugin. modstride assesses Horizon capabilities. An SDK binding and runtime checks need an independently verified implementation. [Horizon APIs](https://github.com/horizon-rust/horizon/blob/main/docs/api/README.md) · [Horizon mods](https://github.com/horizon-rust/horizon/blob/main/docs/mods.md)

Map each feature against initialization, world access, blocks and items, entities, events, scheduling, networking, rendering, resources and persistence.

| Category | Evidence needed |
| --- | --- |
| Direct equivalent | A documented target contract covers the effect with matching lifecycle and authority. |
| Adaptable | A documented contract covers the effect after data, protocol, or execution changes. |
| Reimplementation | Target primitives suffice, but the old implementation depends on Java or engine internals. |
| Unsupported | An essential capability is explicitly unavailable for the selected target. |
| Unknown | API, SDK maturity or behavioral evidence is insufficient to classify the feature. |

Syntax translation can help with pure algorithms that have input/output fixtures. Adapt APIs explicitly and reimplement behavior that depends on class injection, Java references, thread semantics or Minecraft-specific world APIs. Validate resource and save formats independently. Reuse behavior tests across engines where possible and record cases needing manual observation.
