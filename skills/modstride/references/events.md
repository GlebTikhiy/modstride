# Events

Record the trigger, bus or callback, cancellation, ordering, side, thread, and invocation count for each listener. NeoForge has a mod event bus and a gameplay event bus. Fabric API exposes callbacks with behavior defined by the individual callback's contract. A similarly named hook may run before or after vanilla processing or affect downstream listeners. [NeoForge 1.21.1 events](https://docs.neoforged.net/docs/1.21.1/concepts/events/) · [Fabric events](https://docs.fabricmc.net/develop/events/)

Inspect the target invocation site. Check cancellation, threading and behavior when prediction and server handling both run. Prefer a supported callback when its semantics match. If a mixin is required, document injection point and expected invocation count and test with other mods that hook the same method.

Test eligible and ineligible inputs on integrated and dedicated servers. Verify state changes exactly once. For timed logic record tick phase and interval and check pause, dimension change and reconnect.
