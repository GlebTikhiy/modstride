# Agent installation

The canonical [modstride skill](../skills/modstride/SKILL.md) follows the [Agent Skills specification](https://agentskills.io/specification). Install the Python CLI separately and check that `modstride --help` runs from the agent's terminal. The CLI also works in a plain shell. The skill adds guidance for API research, implementation, recovery, and behavioral checks.

## One copy for compatible agents

From a local modstride checkout, run the installer below. Replace the absolute example path with the root of the mod project you will open in the agent. The installer copies the skill and all references. Python accepts forward slashes on Windows.

```text
python scripts/install_skill.py install "D:/Mods/My Mod/.agents/skills"
python scripts/install_skill.py check "D:/Mods/My Mod/.agents/skills"
```

After publication, users with GitHub CLI's skill support can fetch just the skill. Run this in the mod repository and substitute the published GitHub owner. Append `@VERSION` to `modstride` to pin a release tag or commit. [GitHub CLI skill installation](https://cli.github.com/manual/gh_skill_install)

```text
gh skill install OWNER/modstride modstride --agent codex --scope project
```

The shared `.agents/skills/modstride` path works with Codex, Gemini CLI, Cursor, OpenCode and supported Copilot clients. For Claude Code or the Copilot harness in VS Code, use the documented project paths below.

For offline distribution, create the skill-only archive from a checkout and share it with the recipient. Extract it directly into the destination skills directory so the resulting path ends in `modstride/SKILL.md`.

```text
python scripts/install_skill.py export modstride-skill.zip
python -m zipfile -e modstride-skill.zip "D:/Mods/My Mod/.agents/skills"
```

## Agent-specific locations and invocation

The paths below are relative to the mod repository. The paths and client behavior were checked against upstream documentation on November 13, 2026.

| Agent | Project skill location and usage |
| --- | --- |
| OpenAI Codex | Use `.agents/skills/modstride`. Ask Codex to use `$modstride`. Restart Codex if the skill does not appear. [OpenAI skill documentation](https://learn.chatgpt.com/docs/build-skills) |
| Claude Code | Install into `.claude/skills`, then use `/modstride` in a local Claude Code session. Use `~/.claude/skills` for personal installation. [Claude Code skills](https://code.claude.com/docs/en/skills) |
| Gemini CLI | Use `.agents/skills/modstride` or `.gemini/skills/modstride`. Run `/skills reload` and `/skills list` in a running session. Request modstride by name and review its activation prompt. [Gemini CLI skills](https://geminicli.com/docs/cli/skills/) |
| Cursor | Use `.agents/skills/modstride` or `.cursor/skills/modstride`. Search for modstride in the Agent chat slash menu. [Cursor skills](https://cursor.com/docs/skills) |
| GitHub Copilot | Use `.github/skills/modstride` for Copilot on GitHub and for the Copilot harness in VS Code. Open the workspace and ask the agent to use modstride. Copilot CLI also discovers `.agents/skills/modstride`. [GitHub Copilot skills](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills) · [VS Code agent skills](https://code.visualstudio.com/docs/agent-customization/agent-skills) |
| OpenCode | Use `.agents/skills/modstride` or `.opencode/skills/modstride`. Ask OpenCode to load modstride for the migration. [OpenCode skills](https://opencode.ai/docs/skills/) |
| Other compatible agents | Install the complete `modstride` folder into the client's documented discovery directory. Ask the agent to use the skill by name. [Agent Skills client guide](https://agentskills.io/client-implementation/adding-skills-support) |

Keep one source under `skills/modstride`. Use `check` against each project installation made with the local script. If a copy has drifted, move it out of the discovery directory, then install the intended revision. Use GitHub CLI's tracking and update commands for installations managed by `gh skill`. Prefer a single discovery path per agent to avoid loading multiple revisions.

## Example prompts

- “Use modstride to port this Fabric 1.20.1 mod to Fabric 1.20.4. Preserve behavior, create a sibling workspace, build the port and report which runtime checks you could verify.”
- “Use modstride to plan a Forge 1.12.2 to NeoForge 1.21.1 port. Inventory world-save risks and cite evidence for the target APIs before changing code.”
- “Use modstride to assess whether this Java mod can be reimplemented for Horizon. Map features to documented engine capabilities and report unresolved gaps.”
