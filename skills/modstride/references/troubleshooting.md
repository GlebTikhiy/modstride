# Recovery

Start with `modstride resume --workspace WORKSPACE`. Read completed deterministic rules, pending manual operations and verification status. Check the workspace diff and retained logs before repeating an operation. Drift or conflict requires comparing the current file with the plan's preconditions. Preserve successful manual edits and replan in a fresh workspace if the baseline has materially changed.

| Symptom | First diagnostic |
| --- | --- |
| Gradle cannot start or load a plugin | Compare the executing Java, Gradle wrapper distribution, and plugin constraints. |
| Artifact resolution fails | Check the exact coordinate, pinned repository, loader classifier, and reachability. |
| Many symbols disappeared | Confirm namespace and API version before editing references. |
| Client succeeds but server fails on class loading | Trace linkage from shared entry points to client-only classes. |
| Runtime reports failed injection | Check packaged namespace, descriptor and target bytecode. |
| A migrated world loses state | Restore the disposable fixture and inspect registry keys, codec inputs and data ownership. |

Retry after gathering a distinct diagnostic or correcting a demonstrated cause. Record unresolved decisions, remaining operations, and the next concrete action when a prerequisite is unavailable.
