# Run a migration

1. Run `modstride scan SOURCE` and read the confidence and evidence columns. For a JAR you can plan, but applying a plan requires an editable source directory.
2. Run `modstride plan SOURCE --to-version VERSION --to-loader LOADER --output-dir PLAN_DIR`. Pick a plan directory outside the original tree. Review the matrix and operations. Use `--to-mappings` to request a specific namespace or `--to-engine horizon` to assess an engine port.
3. Run `modstride apply --plan PLAN_DIR/migration-plan.json --workspace WORKSPACE --dry-run`. Review the proposed file copy and rule list. Run it again without the flag to create the workspace and apply rules. The destination must be new and disjoint from the source.
4. Review each manual operation and adapt the implementation with version-matched evidence. Use `modstride resume --workspace WORKSPACE --record OPERATION notes/evidence.md` to record a reviewed operation after its dependencies. A nonempty evidence file inside the workspace is required. Human reviewers assess its substance.
5. Run `modstride verify --workspace WORKSPACE`. Add `--run-gradle` only after reviewing the project build logic and launcher. Client, server and gameplay results can be imported separately via `--evidence`.
6. Run `modstride report --workspace WORKSPACE`. Open `.modstride/MIGRATION_REPORT.md` alongside the JSON and Gradle logs. Review the artifact hash, pending work and external evidence before delivery.

After interruption, run `resume`. Use `resume --apply` if creation published the workspace but stopped during rule execution. A changed input produces a drift error. Inspect the file and rerun from a fresh plan if the intended starting point changed. Keep one migration writer active, and pause manual edits while the CLI copies, transforms or verifies.

## Exit codes

- `0` means the requested command ran successfully. Inspect stage statuses for skipped and unavailable checks.
- `1` means verification recorded a failed or blocked stage.
- `2` means invalid arguments, incompatible input, or a command error.

Use the [Copper Token example](../examples/sample-migration/README.md) for concrete commands, a build result and a behavioral test checklist.
