# Add a migration rule

Inspect a built-in rule with `modstride rules show fabric-1204-gradle-minecraft`. Each JSON rule has a schema version, ID, exact source and target selectors, path, preconditions, a typed transformation, postconditions, behavioral differences, limitations, references, confidence, verification evidence, tests, and review status.

The v1 interpreter supports literal and grouped properties in `gradle.properties`, exact JSON string fields in `fabric.mod.json`, and reviewed whole-file replacements of Java source under `src`. It validates paths for portability and rejects duplicate JSON fields, ambiguous assignments, unexpected values and conflicting trusted writes to the same file for the same route. The planner selects trusted rules when source declarations are confirmed. A rule's whole-file before/after hashes and catalogue fingerprint bind execution to the planned input and rule revision.

1. Copy the shape of a built-in rule into an independent rules directory. Start with `status: proposed` and `confidence: experimental` in the JSON.
2. Validate it with `modstride --rules-dir RULES_DIR rules validate`. Use the same global flag before `plan`, `apply` and `resume` when using reviewed external rules.
3. Test precondition failures, preservation of unrelated bytes, repeat execution, and the actual target's relevant verification stage.
4. Submit the rule and evidence for review. A maintainer may set `status` to `trusted` and `confidence` to `verified` after validating evidence. The tool never promotes proposals.

The `--rules-dir` flag delegates trust in the contents of a local catalogue to the operator. Review local rules before use. The `java-source` transformation accepts only the complete reviewed before or after text, with LF and uniform CRLF checkouts supported. Use a manual operation when the helper differs. A rule generalized to arbitrary call sites needs symbol and scope resolution plus dedicated regression coverage.
