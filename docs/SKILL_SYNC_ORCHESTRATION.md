# Skill Sync Orchestration

This note describes a public-safe architecture for synchronizing agent
capabilities across Hermes, OpenClaw-style workspaces, Codex, Gemini CLI,
Claude Code, OpenCode, VS Code, local IDEs, and remote hosts.

It intentionally avoids private machine paths, account ids, memory files,
browser profiles, tokens, and local lockfiles.

## Problem

Agent capability state is split across several formats:

- `SKILL.md` packages and supporting files
- `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, reusable prompts, and system prompts
- MCP server definitions
- commands, hooks, policies, plugin manifests, and agent descriptors
- host-specific files on laptops, VMs, cloud agents, and IDE workspaces

No single client config should become the source of truth. Each tool has its
own native shape, permission model, and discovery rules.

## Recommended Shape

Use a neutral manifest plus native adapters.

```text
asset scanners
  skills, prompts, MCP config, plugins, agents, instructions
        |
        v
canonical manifest + lockfile
        |
        v
policy engine
  visibility, trust, secret scan, target allow/deny
        |
        v
native adapters
  Codex, Gemini, Claude, OpenCode, VS Code, Hermes, OpenClaw
        |
        v
doctor
  parse configs, initialize MCP, list tools, check drift
```

## Manifest Example

```yaml
schema_version: 1
package:
  name: public-agent-skill-layer
  visibility: public
  owner: example-owner

targets:
  codex:
    enabled: true
    emit: config-fragment
  gemini:
    enabled: true
    emit: extension
  claude:
    enabled: true
    emit: mcp-json
  opencode:
    enabled: true
    emit: config-fragment

assets:
  - id: native-mcp
    kind: skill
    path: skills/mcp/native-mcp
    sync_policy: sync
    trust: reviewed
    targets: [codex, gemini, claude, opencode, hermes, openclaw]

  - id: approval-gate-mcp
    kind: mcp_server
    sync_policy: redact
    trust: local
    command: python3
    args:
      - skills/telegram-approval-gate/scripts/telegram_approval_gate.py
    env:
      TELEGRAM_BOT_TOKEN: "<telegram-bot-token-placeholder>"
```

## Sync Policies

- `sync`: reviewed public skills and docs that can be copied or linked.
- `reference`: instructions or prompts that should be transformed per target.
- `redact`: config that can be projected only after secrets are replaced.
- `manual_review`: private, account-bound, memory, auth, session, or ambiguous assets.

Remote sync should be additive by default:

- no destructive deletes
- dereference symlinks when copying to remote hosts
- write generated files atomically
- record hashes in a lockfile after validation
- run doctor checks before and after sync

## Adapter Responsibilities

Adapters should be small and boring. They read the canonical manifest and emit
native config only for their target.

Expected emitters:

- Codex: TOML config fragments and skill directory projections.
- Gemini CLI: `settings.json` fragments or `gemini-extension.json` bundles.
- Claude Code: `.mcp.json`, skill/plugin projections, and command docs.
- OpenCode: JSON/JSONC config fragments.
- VS Code/Copilot: `.vscode/mcp.json` and instruction file fragments.
- Hermes/OpenClaw: skill folders plus explicit local setup notes.

Adapters must not invent permissions. They should fail closed when a manifest
entry is private, unknown, or missing a trust label.

## Doctor Checks

Every sync run should produce an evidence report:

- parse all generated JSON/TOML/YAML
- detect broken symlinks
- detect duplicate skill names and tool name collisions
- initialize MCP servers where safe
- list exposed MCP tools
- compare generated files with current installed config
- flag unpinned package managers and shell commands
- flag secret-like fields before writing public output

This repository includes a small public-safe prototype:

```bash
node scripts/skill-sync-doctor.mjs --root skills --root docs --out /tmp/skill-sync-manifest.json
```

It scans selected roots, fingerprints discovered assets, classifies likely sync
policy, and warns about missing skill frontmatter or symlinks. It does not scan
private home directories unless you explicitly pass them as roots.

Adapter previews can be emitted without installing anything:

```bash
node scripts/skill-sync-doctor.mjs \
  --root skills \
  --out /tmp/skill-sync-manifest.json \
  --emit codex \
  --emit gemini \
  --emit-dir /tmp/skill-sync-generated
```

The generated files are review artifacts, not live config:

- `codex/skills-index.json`
- `gemini/gemini-extension.preview.json`

For local machines that already have multiple agent skill roots, use the
`cross-agent-skill-sync` skill to project reviewed skills additively:

```bash
node skills/software-development/cross-agent-skill-sync/scripts/cross_agent_skill_sync.mjs \
  --target all \
  --strategy symlink
```

It plans first, redacts the home directory in reports, skips existing
destinations, and installs only when `--execute` is provided. Use
`--include-skill /path/to/skill-folder` for local bridge skills that live
outside this repository, and `--require-skill <name>` to prove a required
bridge was found before continuing.

## Browser Automation Routing

Use a routing policy instead of hardcoding one browser workflow:

| Need | Preferred route |
|---|---|
| Disposable web verification | Agent Browser or in-app browser |
| Logged-in Brave session | Brave plus browser-use/CDP, after port preflight |
| Native app or blocked CDP | Computer Use |
| UI research with existing session | Computer Use against Brave |
| Isolated profile testing | dedicated Brave/Chromium user data dir |
| Explicit Comet/Cloak experiment | separate profile, screenshot evidence, no secret export |

Browser preflight should check:

- whether the target port is free
- whether Brave was launched with `--remote-debugging-port`
- whether the account/model/tool mode needed for the task is visible
- whether screenshot capture works
- whether automation will touch private sessions

## Public Repository Boundary

Public repos should contain:

- portable skills
- public docs
- templates
- examples with placeholders
- policy and adapter design
- tests that use fake services or dry-run mode

Public repos should not contain:

- private manifests with real machine paths
- browser profiles
- memory files
- chat exports
- host-specific SSH details
- lockfiles containing private local paths
- live tokens or account ids

## Roadmap

1. Extend `scripts/skill-sync-doctor.mjs` with pluggable scanners.
2. Add trust labels and provenance metadata to the emitted manifest.
3. Add native emitters for Codex and Gemini first.
4. Add Claude, OpenCode, and VS Code emitters.
5. Add MCP doctor checks.
6. Add a dry-run diff command.
7. Add remote host sync with no-delete defaults.
8. Add a local dashboard only after the CLI path is reliable.
