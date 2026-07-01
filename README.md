# Public Agent Skills

<p align="center">
  <img src="assets/awesome-skills-hero.svg" alt="Public Agent Skills animated hero" width="920">
</p>

<p align="center">
  <img src="assets/skill-galaxy.svg" alt="Animated skill galaxy" width="760">
</p>

<p align="center">
  <img src="assets/skill-ribbon.svg" alt="Animated public-safe skill ribbon" width="760">
</p>

<p align="center">
  <a href="https://github.com/Martin-Hausleitner/martins-awesome-skills"><img alt="GitHub" src="https://img.shields.io/badge/GitHub-martins--awesome--skills-181717?logo=github"></a>
  <img alt="Status" src="https://img.shields.io/badge/status-sanitized%20public%20skills-2ea44f">
  <img alt="Agent Skills" src="https://img.shields.io/badge/agent--skills-Hermes%20%2B%20OpenClaw-6f42c1">
  <img alt="Human in the Loop" src="https://img.shields.io/badge/human--in--the--loop-Telegram%20approval-229ED9?logo=telegram">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-blue">
</p>

> A curated, public-safe collection of reusable agent skills for Hermes Agent, OpenClaw-style workspaces, and other skill-compatible coding agents.

This repo is intentionally **not** a dump of a private OpenClaw/Hermes setup. It contains reusable workflows, templates, tests, and docs that are safe to share. Private memories, sessions, chat exports, account ids, real bot tokens, local machine setup, accounting data, and personal automations stay out.

## Contents

- [Highlights](#-highlights)
- [What's Inside](#-whats-inside)
- [Complete Skill Table](#-complete-skill-table)
- [Skill Cards](#-skill-cards)
- [Quick Start](#-quick-start)
- [Purpose-Built Usage Map](#-purpose-built-usage-map)
- [How It Works](#-how-it-works)
- [Featured: Cross-Agent Skill Sync](#-featured-cross-agent-skill-sync)
- [Featured: AI Research Browser + Oracle](#-featured-ai-research-browser--oracle)
- [Featured: Telegram Approval Gate](#-featured-telegram-approval-gate)
- [New Public-Safe Additions](#-new-public-safe-additions)
- [Skill Layout](#-skill-layout)
- [Tests](#-tests)
- [Public Safety Contract](#-public-safety-contract)
- [Docs](#-docs)

## ✨ Highlights

- Human approval gates for external messages
- Dry-run-first Telegram publishing helpers
- Planning, review, debugging, subagent, and TDD playbooks for coding agents
- Cross-agent skill sync for Hermes, Codex, OpenClaw, Gemini, OpenCode, and Claude-adjacent local roots
- GitHub review workflows
- Creative skills for ASCII, Excalidraw, p5.js, songwriting, and AI music workflows
- Research helpers for arXiv, Polymarket, Blogwatcher, Songsee, and YouTube content
- GitHub auth, issues, PR workflow, and review helpers
- Webhook and Notion integration patterns with secret-safe placeholders
- Public-safety audit script included
- GitHub Actions workflow for public safety checks

## 🧰 What's Inside

| Area | Skills | Use For |
|---|---|---|
| 💬 Telegram workflows | `telegram-approval-gate`, `telegram-channel-poster` | Confirm/send/edit/cancel flows and dry-run-first channel publishing |
| 🛠️ Software craft | `plan`, `writing-plans`, `requesting-code-review`, `subagent-driven-development`, `test-driven-development`, `systematic-debugging` | Planning, review, delegation, implementation loops, and debugging |
| 🐙 GitHub | `github-auth`, `github-code-review`, `github-issues`, `github-pr-workflow` | Auth setup, issue triage, structured review, and pull request lifecycle |
| 🎨 Creative tools | `ascii-art`, `excalidraw`, `p5js`, `songwriting-and-ai-music` | Visual explanations, sketches, animations, songs, and terminal-friendly art |
| 🔎 Research | `arxiv`, `blogwatcher`, `comparison-deep-research`, `polymarket`, `songsee`, `youtube-content` | Paper search, market research, comparison scorecards, and blog/video/music discovery workflows |
| 📄 Productivity | `notion`, `ocr-and-documents`, `ai-research-output-publisher` | Notion API patterns, research-result publishing, chat notifications, and OCR/document extraction |
| 📬 Email tooling | `himalaya` | IMAP/SMTP CLI workflows with explicit-send safety |
| 📣 Social media | `hermes-tweet` | Hermes Agent X/Twitter research, read, and gated action workflows through the Hermes Tweet plugin |
| 🧭 Search & analysis | `multi-search-engine`, `tool-comparison-heatmap` | Multi-engine search and comparison visuals |
| 📍 Local discovery | `find-nearby` | Nearby place lookup workflow templates |
| 🔌 MCP | `native-mcp` | Native Model Context Protocol server setup patterns |
| ⚙️ DevOps | `webhook-subscriptions` | Event-driven agent activation with signature and dry-run safety |
| 🔁 Skill sync | `cross-agent-skill-sync` | Share `SKILL.md` packages across local agent roots with dry-run plans |
| 🧪 AI browser E2E | `ai-research-browser-cli`, `ai-research-browser`, `oracle-ai-research-e2e` | Guarded live-CDP provider checks, Oracle reattach evidence, and browser workflow verification |

## 📚 Complete Skill Table

| Skill | Category | What It Helps With |
|---|---|---|
| `telegram-approval-gate` | Messaging | Approval cards before external sends |
| `telegram-channel-poster` | Messaging | Dry-run-first Telegram channel posts |
| `test-driven-development` | Software development | Red/green/refactor discipline for agent work |
| `systematic-debugging` | Software development | Root-cause-first debugging |
| `writing-plans` | Software development | Executable implementation plans |
| `plan` | Software development | Plan-oriented implementation guidance |
| `requesting-code-review` | Software development | Structured code review requests |
| `subagent-driven-development` | Software development | Parallel subagent implementation workflows |
| `cross-agent-skill-sync` | Software development | Sync `SKILL.md` packages across Hermes, Codex, OpenClaw, Gemini, OpenCode, and Claude-adjacent roots |
| `ai-research-browser` | Software development | Guarded browser automation for AI provider research workflows |
| `ai-research-browser-cli` | Software development | Live-CDP workflow operation, restart recovery, screenshots, clipboard output, and status JSON |
| `oracle-ai-research-e2e` | Software development | Oracle 0.13 assist/reattach validation with local safety guards |
| `github-auth` | GitHub | GitHub auth diagnostics without committing secrets |
| `github-code-review` | GitHub | Structured local diff and PR review |
| `github-issues` | GitHub | Issue creation, triage, labels, and closure |
| `github-pr-workflow` | GitHub | Branch, test, commit, push, and PR lifecycle |
| `native-mcp` | MCP | Native Model Context Protocol server setup patterns |
| `webhook-subscriptions` | DevOps | Event-driven agent triggers with signature and dry-run safety |
| `ascii-art` | Creative | Terminal-friendly visual output |
| `excalidraw` | Creative | Hand-drawn style diagrams and visual explanations |
| `p5js` | Creative | Interactive sketches, animations, and exports |
| `songwriting-and-ai-music` | Creative | Songwriting and AI music workflow prompts |
| `arxiv` | Research | Search and summarize arXiv papers |
| `blogwatcher` | Research | Watch and process blog/research updates |
| `comparison-deep-research` | Research | Strict comparison prompts with GitHub links, five weighted categories, diagrams, and `/100` scorecards |
| `polymarket` | Research | Polymarket market data workflows |
| `songsee` | Media | Song and music discovery workflows |
| `youtube-content` | Media | YouTube transcript and content workflows |
| `ai-research-output-publisher` | Productivity | Format completed research results, links, summaries, timing metrics, and optional Notion payloads |
| `notion` | Productivity | Notion API workflow patterns with safe placeholders |
| `ocr-and-documents` | Productivity | OCR and document extraction guidance |
| `himalaya` | Email | Himalaya IMAP/SMTP workflows with explicit-send safety |
| `hermes-tweet` | Social media | Install and operate Hermes Tweet for X/Twitter search, reading, drafting, and gated actions |
| `find-nearby` | Local discovery | Nearby-place lookup workflow templates |
| `multi-search-engine` | Search | Multi-engine search strategy and international search hints |
| `tool-comparison-heatmap` | Analysis | Tool comparison heatmaps and scoring frameworks |

See [docs/SKILL_CATALOG.md](docs/SKILL_CATALOG.md) for the longer catalog notes and public asset list.

## 🌟 Skill Cards

- 💬 **Approval-first messaging**: Telegram buttons before the agent sends anything external.
- 🧪 **Development discipline**: TDD and systematic debugging for agents that need less drama and more evidence.
- 🧩 **Agent orchestration**: plans, subagents, and review loops for larger work.
- 🎨 **Visual creation**: ASCII, Excalidraw, and p5.js workflows for fast diagrams and explainers.
- 🔬 **Research workflows**: arXiv, Polymarket, and YouTube content helpers.
- 🔌 **Tool plumbing**: MCP setup patterns and multi-search utilities.
- 📣 **Social workflows**: Hermes Tweet setup and action-gated X/Twitter workflows.
- 🔁 **Skill sharing**: additive, dry-run-first projection into local Hermes/Codex/agent skill roots.
- 🐙 **GitHub operating loop**: auth, issues, PRs, and review workflows in one public-safe set.
- ⚙️ **Event bridges**: webhook subscriptions with HMAC-first thinking.
- 🧱 **Reusable templates**: start new skills from `templates/SKILL_TEMPLATE.md`.

## 🧭 Purpose-Built Usage Map

This repo is meant to be useful to a stranger before they know your local setup.
Start with the task, choose the matching skill, then run the safest command that
proves the environment before doing real work.

| If You Need To... | Use This Skill | First Safe Action | Success Proof |
|---|---|---|---|
| Share skills across local agents | `cross-agent-skill-sync` | `--target all` dry-run | Manifest shows intended roots and no conflicts |
| Run Gemini or ChatGPT browser research | `ai-research-browser-cli` + `ai-research-browser` | `real-session-preflight` | `can_attach=true`, verified owner/profile, account/plan evidence |
| Supervise a long browser research run | `oracle-ai-research-e2e` | `oracle-plan` or `--oracle-mode assist` | Oracle `status`, `reattach`, and session-render commands in artifacts |
| Publish completed research output | `ai-research-output-publisher` | `render` into local files | Markdown message plus optional Notion payload, no external write by default |
| Compare tools, repos, or products | `comparison-deep-research` | Generate a structured prompt | Linked candidates, five weighted categories, `/100` scorecard |
| Send anything external | `telegram-approval-gate` | Dry-run approval card | Human clicked send/edit/cancel; no silent send |
| Work on code safely | `plan`, `test-driven-development`, `systematic-debugging` | Read the skill and run local tests | Red/green/test evidence before final report |

```mermaid
flowchart TD
  Task["User intent"] --> Pick["Pick purpose-built skill"]
  Pick --> Preflight["Dry-run / preflight"]
  Preflight --> Guard{"Proof available?"}
  Guard -- no --> Stop["Stop with blockers and next steps"]
  Guard -- yes --> Execute["Run scoped workflow"]
  Execute --> Evidence["Write status, tests, screenshots, or payloads"]
  Evidence --> Report["Report exact result and limits"]
```

For browser automation, do not infer success from a click or a port number. The
workflow is only successful when the status artifacts prove the intended account,
provider feature, isolated automation target, and final output.

```mermaid
sequenceDiagram
  participant Agent
  participant CLI as ai_research_browser.py
  participant Browser as Real Browser CDP
  participant Provider as AI Provider UI
  participant Oracle as Oracle Assist
  participant Artifacts

  Agent->>CLI: real-session-preflight
  CLI->>Browser: verify CDP owner/profile
  Browser-->>CLI: attach_port + target capability
  CLI->>Provider: open isolated automation target
  Provider-->>CLI: login/account/plan/feature evidence
  CLI->>Oracle: write status/reattach plan
  CLI->>Artifacts: status.json + screenshot + redacted logs
  Artifacts-->>Agent: proof or blocker
```

Safe browser automation rule of thumb:

- `9333` is only a preferred Comet port. If it belongs to VS Code or another
  process, use `alternate_cdp.attach_port` when discovered, or run
  `browser-cdp-recover --dry-run`.
- Deep Research, Agent, image generation, and other quota-spending modes require
  explicit `--allow-paid-quota-use` and must still pass account/plan/feature
  guards before submit.
- A real Deep Research result means the run has a provider start marker, a
  completion marker, extracted output text, and a stored chat/result link.

## 🚀 Quick Start

Clone the repo:

```bash
git clone https://github.com/Martin-Hausleitner/martins-awesome-skills.git
cd martins-awesome-skills
```

Copy a skill into your local agent skill directory:

```bash
mkdir -p ~/.hermes/skills/messaging
cp -R skills/telegram-approval-gate ~/.hermes/skills/messaging/
```

For Codex/OpenClaw-style workspaces, copy into the workspace skill folder:

```bash
mkdir -p ~/.codex/skills
cp -R skills/software-development/ai-research-browser-cli ~/.codex/skills/

mkdir -p ~/.openclaw/workspace/skills
cp -R skills/telegram-channel-poster ~/.openclaw/workspace/skills/
```

See [docs/INSTALL.md](docs/INSTALL.md) for Codex, Claude, Gemini, OpenCode, Hermes, and cross-agent sync installs.

See [docs/CROSS_AGENT_INSTALL_PROOF.md](docs/CROSS_AGENT_INSTALL_PROOF.md) for the current proof matrix showing the core AI research skills installed across Hermes, Codex, OpenClaw, Gemini, OpenCode, Claude, and generic Agents roots.

## 🧭 How It Works

No private screenshots are needed. The repo uses public-safe diagrams and generated visuals to show the architecture without exposing accounts, browser tabs, local machine paths, prompts, or personal data.

<p align="center">
  <img src="assets/skill-lifecycle.svg" alt="Skill lifecycle from creation through validation, install, and improvement" width="920">
</p>

```mermaid
flowchart LR
  A["Portable SKILL.md folder"] --> B["Public-safe scanner"]
  B --> C["Manifest + hashes"]
  C --> D["Target adapters"]
  D --> E["Hermes"]
  D --> F["Codex"]
  D --> G["OpenClaw"]
  D --> H["Gemini / OpenCode"]
  D --> I["Claude-adjacent bridge"]
```

```mermaid
sequenceDiagram
  participant User
  participant CLI as cross-agent-skill-sync
  participant Audit as Safety Audit
  participant Roots as Local Agent Roots

  User->>CLI: plan sync
  CLI->>CLI: discover SKILL.md folders
  CLI->>Audit: redact and classify report
  Audit-->>CLI: safe plan
  User->>CLI: execute after review
  CLI->>Roots: add missing symlinks only
  Roots-->>User: skills available after agent refresh
```

<p align="center">
  <img src="assets/public-safety-pipeline.svg" alt="Public-safe publish pipeline from scan to publish" width="920">
</p>

## 🔁 Featured: Cross-Agent Skill Sync

`cross-agent-skill-sync` shares reviewed `SKILL.md` packages across local agent ecosystems without copying private state. It is built for Hermes, Codex, OpenClaw-style workspaces, Gemini CLI, OpenCode, Claude-adjacent roots, and other local skill-compatible agents.

<p align="center">
  <img src="assets/cross-agent-skill-sync.svg" alt="Cross-agent skill sync architecture" width="920">
</p>

Safe defaults:

- **Plan first:** no filesystem writes unless `--execute` is passed.
- **No overwrites:** existing skill folders are reported as `exists` or `conflict`, not replaced.
- **Private-path redaction:** reports hide the home directory by default.
- **Bridge-friendly:** local skills outside this repo can be included with `--include-skill`.
- **Public-safe:** the repo ships deterministic tests and an audit script before publish.

```mermaid
flowchart TD
  Start["Run dry-run plan"] --> Check{"Warnings or conflicts?"}
  Check -- yes --> Review["Manual review; no writes"]
  Check -- no --> Execute["Run with --execute"]
  Execute --> Link["Create missing symlinks/copies"]
  Link --> Verify["Run plan again"]
  Verify --> Done["All destinations exist"]
```

Plan a local projection:

```bash
node skills/software-development/cross-agent-skill-sync/scripts/cross_agent_skill_sync.mjs \
  --target all \
  --require-skill cross-agent-skill-sync
```

Execute an additive same-machine sync after review:

```bash
node skills/software-development/cross-agent-skill-sync/scripts/cross_agent_skill_sync.mjs \
  --target all \
  --strategy symlink \
  --execute
```

## 🧠 Featured: AI Research Browser + Oracle

`ai-research-browser` is the repo's most advanced browser-automation skill. It coordinates real Brave/Comet/Chrome CDP sessions, provider login/plan/model guards, ChatGPT/Gemini Deep Research workflows, rate-limit-safe pacing, and Oracle 0.13 long-run supervision.

<p align="center">
  <img src="assets/ai-research-browser-oracle-stack.svg" alt="AI Research Browser plus Oracle 0.13 architecture" width="920">
</p>

<p align="center">
  <img src="assets/ai-research-browser-proof-cards.svg" alt="Sanitized proof cards for Oracle and AI Research Browser integration" width="920">
</p>

Why it matters:

- **Real-session first:** `workflow-run --strategy auto` prefers verified live CDP and refuses silent clone/sibling fallback for real ChatGPT/Gemini E2E.
- **Oracle as supervisor:** `--oracle-mode assist|runner` adds `@steipete/oracle@0.13.0` status, reattach, and session-render commands to the same workflow payload.
- **Local guards stay in charge:** Oracle cannot bypass login, account, plan, feature, screenshot, paid-quota, challenge, rate-limit, or ChatGPT model-safety checks.
- **Cost safety:** ChatGPT Pro/Extended Pro/GPT-5.5 Pro are blocked before typing in automated tests; non-Pro Thinking, Agent, and Deep Research paths are preferred.
- **Evidence-first:** runs write `status.json`, screenshot paths, target ids, redacted command logs, and Oracle reattach instructions.
- **Hermes-testable:** `oracle-ai-research-e2e` installs as a local Hermes skill and ships a deterministic checker for the combined GitHub/local workflow.

```mermaid
flowchart LR
  Preflight["Live CDP + account guards"] --> Target["Isolated automation target"]
  Target --> Provider["ChatGPT / Gemini workflow"]
  Provider --> Oracle["Oracle status + reattach"]
  Oracle --> Evidence["Redacted status artifacts"]
  Evidence --> Audit["Public-safe proof"]
```

Try a public-safe Oracle plan:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py oracle-plan \
  --prompt "Review the current failed E2E browser workflow." \
  --provider chatgpt \
  --mode deep-research \
  --remote-chrome 127.0.0.1:9223 \
  --research-depth deep \
  --browser-attachment-timeout 240
```

Run the guarded integration path:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-run \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --mode agent \
  --strategy auto \
  --oracle-mode assist \
  --allow-paid-quota-use \
  --prompt "Debug why Oracle reattach should supervise long browser research."
```

Read the full skill docs: [AI Research Browser](skills/software-development/ai-research-browser/README.md).

Run the dedicated local proof skill:

```bash
python3 skills/software-development/oracle-ai-research-e2e/scripts/oracle_ai_research_e2e_check.py --quick --json
```

## 💬 Featured: Telegram Approval Gate

`telegram-approval-gate` makes external communication safer. Before an agent sends a message, post, reply, or email, it routes the final draft through Telegram buttons:

```text
Senden      Bearbeiten
Abbrechen
```

Local fake-Telegram E2E test:

```bash
python3 skills/telegram-approval-gate/tests/test_telegram_approval_gate.py
```

Dry run:

```bash
python3 skills/telegram-approval-gate/scripts/telegram_approval_gate.py \
  --dry-run \
  --title "Approval Preview" \
  --draft "Ship this?"
```

Live use needs a **dedicated approval bot**, not the same bot token used by a running Hermes/OpenClaw gateway:

```bash
cp config-templates/hermes-approval.env.example .env.telegram-approval
```

Then fill the copied private file with your own values. Do not commit it.

## 🆕 New Public-Safe Additions

- `github-auth`: diagnose and configure GitHub access without leaking tokens.
- `github-issues`: create, triage, label, and close issues with clean public summaries.
- `github-pr-workflow`: branch, commit, test, push, and open pull requests.
- `ai-research-browser-cli`: operate the guarded `ai_research_browser.py` CLI for Brave/Comet live-CDP checks, restart recovery, screenshots, clipboard output, and E2E evidence.
- `ai-research-output-publisher`: render finished research jobs as polished chat messages, copy buttons, metrics, and optional Notion pages.
- `comparison-deep-research`: turn broad product/package/repo comparisons into strict Deep Research prompts with linked candidates, five weighted categories, and `/100` scorecards.
- `webhook-subscriptions`: design event-driven agent triggers with explicit signature checks.
- `notion`: use the Notion API with placeholder-only examples and narrow permissions.
- `templates/SKILL_TEMPLATE.md`: a safe starting point for new skills.
- `.github/workflows/public-safety.yml`: CI guardrail for audit and Telegram tests.
- `docs/SKILL_SYNC_ORCHESTRATION.md`: public-safe plan for syncing skills, MCP servers, prompts, and agent configs across tools.
- `scripts/skill-sync-doctor.mjs`: prototype inventory/doctor for public-safe skill sync manifests.
- `cross-agent-skill-sync`: local projector that can install reviewed skills into discovered agent roots without overwrites.

Run the skill sync prototype:

```bash
node scripts/skill-sync-doctor.mjs --root skills --root docs --out /tmp/skill-sync-manifest.json
node scripts/skill-sync-doctor.mjs --root skills --emit codex --emit gemini --emit-dir /tmp/skill-sync-generated
```

Plan a local additive projection into known agent roots:

```bash
node skills/software-development/cross-agent-skill-sync/scripts/cross_agent_skill_sync.mjs --target all
```

Render a finished research batch into a chat-ready message and Notion payload:

```bash
python3 skills/productivity/ai-research-output-publisher/scripts/ai_research_output_publisher.py render \
  --input /tmp/research-results.json \
  --message-output /tmp/research-message.md \
  --payload-output /tmp/research-notion-payload.json
```

Generate a reusable comparison Deep Research prompt:

```bash
python3 skills/research/comparison-deep-research/scripts/comparison_deep_research_prompt.py \
  --topic "Best Obsidian AI plugins" \
  --use-case "Notion-like team knowledge workflows" \
  --candidate-count 50
```

## 🗂️ Skill Layout

```text
skills/
  analysis/
    tool-comparison-heatmap/
  creative/
    ascii-art/
    excalidraw/
    p5js/
    songwriting-and-ai-music/
  devops/
    webhook-subscriptions/
  email/
    himalaya/
  github/
    github-auth/
    github-code-review/
    github-issues/
    github-pr-workflow/
  leisure/
    find-nearby/
  mcp/
    native-mcp/
  media/
    songsee/
    youtube-content/
  productivity/
    ai-research-output-publisher/
    notion/
    ocr-and-documents/
  research/
    arxiv/
    blogwatcher/
    comparison-deep-research/
    polymarket/
  search/
    multi-search-engine/
  software-development/
    ai-research-browser/
    ai-research-browser-cli/
    cross-agent-skill-sync/
    oracle-ai-research-e2e/
    plan/
    requesting-code-review/
    subagent-driven-development/
    systematic-debugging/
    test-driven-development/
    writing-plans/
  telegram-approval-gate/
  telegram-channel-poster/
```

Every skill keeps its own `SKILL.md` as the entry point. Larger references and deterministic helpers live next to the skill under `references/`, `scripts/`, or `templates/`.

## ✅ Tests

Run the currently bundled executable tests:

```bash
python3 skills/telegram-approval-gate/tests/test_telegram_approval_gate.py
(cd skills/telegram-channel-poster && python3 scripts/test_telegram_channel_post.py)
python3 -m unittest discover -s skills/software-development/ai-research-browser/tests -p 'test_ai_research_browser.py'
python3 -m unittest discover -s skills/software-development/oracle-ai-research-e2e/tests -p 'test_*.py'
python3 skills/software-development/oracle-ai-research-e2e/scripts/oracle_ai_research_e2e_check.py --quick --json
python3 -m unittest discover -s skills/productivity/ai-research-output-publisher/tests -p 'test_*.py'
python3 -m unittest discover -s skills/research/comparison-deep-research/tests -p 'test_*.py'
node --test tests/skill-sync-doctor.test.mjs
node --test skills/software-development/cross-agent-skill-sync/tests/cross_agent_skill_sync.test.mjs
```

Run the public safety scan:

```bash
scripts/audit-public-safety.sh
```

## 🔐 Public Safety Contract

This repo should never contain:

- real `.env` files
- bot tokens, GitHub tokens, OAuth secrets, private keys, cookies, or auth databases
- `MEMORY.md`, `USER.md`, private session logs, chat exports, transcripts, or trajectory files
- accounting, health, location, clipboard, Find My, or personal automation data
- machine-specific paths from a private setup

See [docs/SECURITY.md](docs/SECURITY.md) for the full checklist.

## 📚 Docs

- [Skill Catalog](docs/SKILL_CATALOG.md)
- [Install Skills](docs/INSTALL.md)
- [Security Checklist](docs/SECURITY.md)
- [Contributing Skills](docs/CONTRIBUTING_SKILLS.md)
- [Private Setup Boundary](docs/PRIVATE_SETUP_BOUNDARY.md)
- [Gallery](docs/GALLERY.md)
- [Release Checklist](docs/RELEASE_CHECKLIST.md)
- [Skill Template](templates/SKILL_TEMPLATE.md)

## 💡 Why This Exists

Agent skills are a lovely little format: small, searchable, portable, and easy to test. This repo collects the useful parts of real workflows while leaving the private operational surface behind the curtain where it belongs.

Build sharp tools. Keep secrets boring. Let the buttons save you from accidental sends.
