# Research, port and propose an API rule

## Investigate an undocumented break

1. Reproduce on a disposable baseline and target with pinned Minecraft, loader, mappings, Gradle and JDK. Capture the first failing compiler diagnostic or runtime call chain. Record source and target symbols with owner and descriptor, plus side, thread, lifecycle and data format when they matter.
2. Compare the version-specific upstream API, mapped dependency artifacts, and the loader's patch or test source. Use `javap` when docs omit a signature. Look at call sites to establish timing and semantics. Treat similar names as leads and resolve uncertainty with a narrow compile or runtime probe.
3. Write a small feature contract before changing source. State the input, result, defaults, persisted values and failure behavior. Identify cases that require a real client, server, saved world or multiplayer pair. Keep unsupported cases in the plan.
4. Implement one API seam at a time and verify against the baseline. Record the actual command, version, result and log path using `resume --record OPERATION PATH`. Keep changes to storage, resources and code separate when possible so failure evidence identifies the responsible subsystem.

## Submit a reusable rule

Record the exact supported pattern and when it must refuse. Prefer a semantic transform with explicit symbol resolution when generalizing across projects. For a reviewed exact Java helper, the `java-source` rule can record the whole original and replacement. Include a positive fixture and a drift or near-match case. Demonstrate the same observable behavior on both builds. Supply references, evidence and remaining limitations. Use `status: proposed` with `confidence: experimental` for review, and validate with `modstride --rules-dir RULE_DIR rules validate`. Maintain separate rules when a change requires distinct runtime evidence.
