# Workflow and handoff

Build a feature inventory from source and observation. One row should identify its triggering event, side and thread, inputs and state, output visible to players, persistence and synchronization, source evidence and a target acceptance test. Inspect generated code and resources, optional dependencies, and differences between physical client, integrated server and dedicated server.

Give each subsystem a compatibility row with source implementation, target evidence, change strategy, risk, operation IDs, prerequisites, and verification. Include initialization, registries, blocks/items, entities, world generation, events, networking, rendering, menus, configuration, persistence, commands, resource and data packs, bytecode transformations, and integrations. Record which are absent or require further inspection.

Work in dependency order. Establish target metadata and dependency resolution, then registration and initialization, then mechanics, storage, multiplayer, and presentation where that order fits the mod. Keep each operation tied to an acceptance check. Retain choices around behavior changes, world-save compatibility, and unavailable integrations.

The CLI owns `.modstride/state.json`. Keep the JSON plan and related Markdown together. Maintain a workspace note for manual tasks that records the operation ID, decisions, file paths, evidence, and the next operation. When a manual operation meets its verification criteria, record the reviewed evidence with `modstride resume --workspace WORKSPACE --record OPERATION relative/evidence.md`. Keep the evidence file inside the workspace. Re-read the diff and evidence after resuming. Re-run checks whose inputs changed.

A single agent can perform all phases. When the host and user authorize delegation, a researcher can pin APIs and dependencies, an implementer can edit assigned subsystems, a validator can check evidence independently, and a coordinator can reconcile the plan and changes. Give writers disjoint file ownership and verify integration.

After a reusable change works, remove project identifiers from the rule proposal. Include source and target coordinates, exact pattern and preconditions, behavior differences, scope limits, upstream sources, and a regression fixture. Validate the schema and check overlapping rules before review.
