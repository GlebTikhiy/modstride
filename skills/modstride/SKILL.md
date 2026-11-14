---
name: modstride
description: Plan, implement, resume, and verify a port of an existing Minecraft mod across Minecraft versions, loaders, or mappings. Use when preserving gameplay behavior or assessing whether a Java mod can be reimplemented for another engine such as Horizon.
license: MIT
compatibility: Requires Python 3.11+, the modstride CLI, and filesystem and shell access. Source editing needs a permitted source checkout. API research and build dependencies may need network access. Java builds require the target project's compatible JDK and build tool.
---

# modstride

Use this skill to migrate an existing mod. Establish the exact target Minecraft version and loader, or engine and release. Use static analysis for JAR-only inputs. Source reconstruction and redistribution need appropriate rights. Work in an isolated sibling workspace, preserve the original project, and use disposable worlds or copies of existing saves.

## Migration sequence

1. **Reconnaissance.** Run `modstride scan SOURCE --format json`. Read entry points, build and settings files, resource generators, dependencies, and relevant source sets. Inventory observable features and the data they create. Resolve scan ambiguity with declared build settings or dependency artifacts. Treat source signatures and guessed namespaces as leads.
2. **Target research.** Pin the game, loader, mappings, Java, and Gradle coordinates. Inspect the exact API and its call sites or a version-matched upstream example. Record source URL or artifact, version, owner, descriptor, side, thread, and failure behavior as relevant. Mark missing or contradictory API evidence as unresolved and leave dependent changes pending.
3. **Compatibility and strategy.** Run `modstride plan SOURCE --to-version VERSION --to-loader LOADER --output-dir PLAN_DIR`. Supply `--to-mappings` when explicitly migrating namespaces. For an engine assessment, use `--to-engine horizon` in place of `--to-loader`. Read the JSON plan, Markdown plan, and compatibility matrix. Choose direct port, replacement API, staged migration, or reimplementation per subsystem and record the reason.
4. **Implementation.** Read applicable rules with `modstride rules show RULE_ID`. Preview with `modstride apply --plan PLAN_DIR/migration-plan.json --workspace WORKSPACE --dry-run`, then run the same command without `--dry-run` to create the isolated workspace. Review the diff and outcome. Implement manual operations in dependency order using small changes and verified APIs. Record manual progress and evidence alongside the machine-managed state.
5. **Verification and gameplay.** Run `modstride verify --workspace WORKSPACE` for static checks. Review build scripts and repositories before using `--run-gradle`. Test source and target under comparable conditions. Capture dedicated server startup and a separate client startup where applicable. Check gameplay, data reload, and multiplayer independently. Follow [Testing and gameplay parity](references/testing.md).
6. **Delivery.** Run `modstride report --workspace WORKSPACE`. Record the workspace, artifact if built, actual check results, regressions, pending work, exact toolchain and reproduction commands. Call out unverified behavior and migration limits by feature. Propose reusable rules after documenting provenance, limits and regression tests for review.

## Recovery and handoff

Run `modstride resume --workspace WORKSPACE` and compare its status against the plan, diff and evidence. Replay an interrupted deterministic operation with `resume --apply` after resolving reported conflicts. Classify the first actionable error and collect a distinct diagnostic before retrying a failed build. Record the blocker and next check when an API, dependency, build tool or test environment is missing. See [Recovery](references/troubleshooting.md).

## References

- [API research and rule proposals](references/api-research.md) for undocumented breaks, version-pinned experiments, Java changes and review evidence.

- [Workflow and handoff](references/migration-workflow.md) for the compatibility matrix, checkpoints and optional roles.
- [Version migration](references/version-migration.md) for large jumps, toolchains and resource changes.
- [Loader migration](references/loader-migration.md) for entry points, lifecycle, capabilities and configuration.
- [Mapping migration](references/mapping-migration.md) for Mojang mappings, Yarn, Intermediary and MCP/SRG.
- [Registries](references/registries.md), [events](references/events.md), and [networking](references/networking.md) for server-authoritative features.
- [Rendering](references/rendering.md), [world data](references/world-data.md), and [mixins and transformers](references/mixins-and-transformers.md) when the inventory contains those subsystems.
- [Java to Rust](references/java-to-rust.md) for engine capability assessment.
