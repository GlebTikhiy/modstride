# Working on modstride

Use the installable Python CLI as the entry point. Keep Python 3.11 compatibility and keep runtime dependencies minimal. Preserve the direction from CLI orchestration into scanner, planner, rules, workspace, verification and reporting.

Treat JAR scanning as read-only static inspection. Use a disposable copy for sample builds and original worlds. Keep build execution opt-in. Keep confirmed declarations distinct from heuristic observations. Require target-specific evidence for automatic transformations.

Keep the skill canonical under `skills/modstride`. Update docs when CLI or state contracts change. Before delivery run `python -m pytest`, `ruff check .`, `ruff format --check .`, `modstride rules validate`, and the official skill validator if the skill changed. Record what was actually verified.
