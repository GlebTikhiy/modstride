# Contributing

Install the development extras with `python -m pip install -e ".[dev]"`. Run `python -m pytest`, `ruff check .`, `ruff format --check .`, and `modstride rules validate`. For skill edits, run the official `skills-ref validate skills/modstride` validator. CI pins the validator revision.

## Migration rules

Start with one reproducible source and target change. Generalize the narrowest proven pattern, remove project-specific identifiers, cite exact upstream versions, and record what the change implies for behavior. Submit a proposed rule, a failing-before regression test and evidence from a disposable project. A maintainer can mark the rule trusted after reviewing the evidence and tests. [Rule contract](docs/adding-rules.md)

## Loaders, targets and mappings

Extend static parsing with minimal metadata fixtures and confidence tests. Add a target profile only with upstream references, a capability assessment and validation instructions. Engine profiles implement subsystem assessment via the target adapter interface. Build support requires an observed integration test with a pinned SDK or toolchain.

Document a mapping's provenance, namespace names, release, license and signature tests. Reference upstream mapping artifacts when redistribution terms limit bundling. Use synthetic entries only as explicitly synthetic parser fixtures.

## Skills and examples

Edit the canonical skill and link version-specific details in focused references. Reproduce example commands in a new workspace. Submit original or redistributable source with attribution, version pins, expected behavior and a record of actual checks.

For compatibility issues, include source and target versions, modstride and Java versions, relevant redacted scan facts, a minimal reproducer and the failing stage. Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).
