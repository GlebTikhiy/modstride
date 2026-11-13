# Networking

Inventory packet IDs, schema and size limits, phase, direction, authorization, handshake/version policy, and expected recipients. Preserve server authority. Validate entity existence, ownership, range, and relevant game state before processing a client request. Verify the actual handler thread and schedule work on the correct game thread when needed.

Forge 1.20.1 documents the SimpleImpl channel API. NeoForge 1.21.1 registers payloads with a `PayloadRegistrar` obtained during `RegisterPayloadHandlersEvent` and associates them with stream codecs. Confirm direction, phase and thread for each payload against the pinned API. [Forge 1.20.1 SimpleImpl](https://docs.minecraftforge.net/en/1.20.1/networking/simpleimpl/) · [NeoForge 1.21.1 payloads](https://docs.neoforged.net/docs/1.21.1/networking/payload/) · [Fabric networking](https://docs.fabricmc.net/develop/networking/)

Round-trip valid messages and test malformed messages, unauthorized requests, reconnects, late-joining clients and unsupported peer versions. Document protocol breaks and verify the failure is explicit. Check entity tracking and persistence independently of packet transport.
