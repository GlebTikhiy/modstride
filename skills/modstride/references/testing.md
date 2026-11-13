# Testing and gameplay parity

For each feature record baseline versions and dependencies, initial world and player state, triggering actions, expected observable result, network observers and persistence checkpoints. Example for a placed machine:

| Step | Observation |
| --- | --- |
| Place it and insert one input item | A dedicated server owns the input. A second client sees the correct machine state. |
| Wait the baseline tick count | The correct output appears once and the input is consumed once. |
| Save and reload a disposable world | Remaining input, output and progress restore as expected. |
| Try a disallowed interaction | The server rejects it and both clients remain consistent. |

Capture evidence per stage. Validate metadata and resources first, then dependency resolution, compilation and unit tests. Inspect the produced artifact and record its path and hash. Run target-specific server and client launch checks with a reviewed configuration. Then run gameplay tests in disposable worlds and compare observations against the baseline. Record reload behavior with old-world copies when compatibility matters.

To attach external checks, write a JSON object keyed by `dedicated-server`, `client` or `gameplay`. Each entry needs a `status`, a brief `detail` describing the observation, and a `path` to a nonempty evidence file relative to the workspace. Pass the JSON file to `modstride verify --workspace WORKSPACE --evidence EVIDENCE_JSON`. The CLI records the supplied outcomes with external provenance. Review the underlying logs or observations before recording a pass.

Use Passed when the named stage ran and its assertion succeeded. Failed means an attempted check failed. Skipped indicates intentional omission. Blocked identifies a missing prerequisite. Not available indicates the check has no applicable or configured facility. Store commands, environment, versions and sanitized evidence paths. Mark runtime and parity incomplete whenever corresponding evidence is absent.
