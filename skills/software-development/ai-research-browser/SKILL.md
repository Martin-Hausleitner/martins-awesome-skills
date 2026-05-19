---
name: ai-research-browser
description: Discover local Brave, Comet/Komet, Chrome, or Edge profiles and run ChatGPT/Gemini research or agent workflows with hidden/headless launch arguments and screenshot-backed E2E records.
version: 0.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [browser, brave, comet, chatgpt, gemini, deep-research, agent, e2e]
    related_skills: [browser-profile-routing, ai-research-ui-fallbacks, google-deep-researcher]
---

# AI Research Browser

Use this skill when the user wants Hermes to run AI chat, Deep Research, or Agent flows through an installed browser profile, especially Brave or Comet/Komet.

The helper CLI is:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py
```

## What It Does

- Discovers installed Chromium-family browsers: Brave, Comet/Komet, Google Chrome, Microsoft Edge, Opera, and ChatGPT Atlas.
- Reads Chromium profile metadata from `Local State` and `Preferences`, including profile directory, display name, and visible account email when available.
- Resolves profile aliases such as `work` by exact profile/account match first, then by a Work/Arbeit name match.
- Produces launch arguments for headless or background runs with `--remote-debugging-port`, `--user-data-dir`, and `--profile-directory`.
- Starts launchable browsers hidden in the background via macOS `open -g -j`, with optional true headless mode and a dry-run JSON plan before execution.
- Supports provider modes for ChatGPT chat, ChatGPT Deep Research, ChatGPT Agent, Gemini chat, Gemini Deep Research, Gemini Agent, Claude chat/research/artifacts, Perplexity research, and Grok/Grog research.
- Builds a full browser x profile x provider x feature test matrix for systematic E2E runs.
- Provides an interactive wizard that lets a human choose the installed browser, profile, provider, and feature before launching or testing.
- Archives existing provider chats into a local cache so later runs can continue from cached transcripts or intentionally refresh by scraping again.
- Reopens cached/existing chat URLs with `workflow-followup`, sends a follow-up such as "Fass zusammen", exports Markdown, and refreshes the local cache.
- Attaches local files/images to `workflow-run` and `workflow-followup` when the provider exposes a visible file input, and records `no-file-input` instead of guessing when the upload path is hidden.
- Discovers installed SaveAI / AI Exporter extension manifests and can copy/load selected extensions into temporary profile clones for export-oriented tests.
- Reverse-engineers installed SaveAI / AI Exporter capabilities, including supported provider hosts, Markdown/PDF/JSON/image export actions, Notion sync actions, and local Notion session evidence without cookie values.
- Extracts visible provider account, plan/subscription, model, quota, and usage text when a real UI snapshot is supplied.
- Scans local profile site data for provider session evidence without reading or emitting cookie values.
- Runs a real-session preflight that checks CDP reachability, default-port ownership, already-running browsers without remote debugging, and provider session evidence before any paid workflow is claimed as usable.
- Runs Agent Browser backed E2E probes against a CDP-enabled browser profile and records provider inventory artifacts.
- Runs an Agent Browser live suite against a real CDP-enabled browser session and can fail hard when the page is signed out or blocked.
- Fills a provider composer through Agent Browser, optionally submits the prompt, exports the visible output, and saves it into the local chat cache.
- Builds a focused primary feature suite for ChatGPT chat/model selection, ChatGPT Deep Research, ChatGPT Agent, Gemini Deep Research, Claude Opus, Grok chat/research, and Perplexity chat/research.
- Runs Agent Browser against disposable browser-profile clones and records `signed-out-or-wall` when the cloned session hits login or anti-automation pages.
- Exposes provider-specific probe hints for account menus, model selectors, tool controls, and usage/limit text.
- Lists automation backends such as Playwright/CDP, Codex Computer Use, Peekaboo, Unbrowser Local, OpenAI CUA/Operator, Claude Computer Use, Gemini Computer Use, Stagehand, Browser-Use, and Hyperbrowser.
- Lists Peter Steinberger's Oracle as an optional consult backend for multi-model review, browser-session reattach, Deep Research, and session artifacts.
- Lists selectable model/tool catalogs for ChatGPT, Gemini/Google, Claude/Anthropic, Perplexity, and Grok/xAI.
- Marks profiles as `signed-in-hidden` when browser metadata indicates account/session state but no email is exposed.
- Reports `app_exists`, `binary_exists`, and `user_data_exists` so stale browser profile data is not confused with a launchable installed browser.
- Records E2E evidence as a `status.json` plus screenshot path, so a human can verify whether the provider UI actually entered the requested mode.

## Safety Rule

Do not quit or relaunch the user's already-open browser without explicit permission. If a browser is already running without `--remote-debugging-port`, run preflight and report the blocker. Prefer `launch-background --dry-run` or `launch-all-background --dry-run` before execution, so the user can see whether the run will attach, launch hidden, or be blocked. For live UI checks, use Computer Use against the existing window and record screenshots locally.

For Agent Browser "truth" checks, prefer `agent-browser-live-suite --assert-login` against a known real CDP port. Do not trust `agent-browser --auto-connect` unless the captured provider UI proves the intended profile/account is logged in; auto-connect can attach to a signed-out clone or the wrong Chromium instance.

Do not commit private screenshots that contain account names, chat history, or private prompts to a public repository. Keep them as local artifacts unless the user explicitly asks for a sanitized export.

## Commands

Discover browsers, profiles, providers, modes, and known model labels:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py discover
```

Build the full test matrix:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py matrix --json --backend playwright-cdp
```

List automation backends:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py backends
```

List installed SaveAI / AI Exporter extension copies:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py extensions --ai-exporter
```

Inspect SaveAI / AI Exporter export and Notion-sync readiness:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py ai-exporter-capabilities \
  --output /tmp/hermes-ai-exporter-capabilities.json
```

The capability command reports supported providers, extension actions such as `exportFullMarkdown`, `copyFullMarkdown`, `openFullNotionExport`, and `saveFullChatsToNotion`, and whether Notion site cookies indicate a logged-in workspace. Treat Notion sync as an external write: export/cache locally first, then perform Notion sync only when the user requested that write.

Generate the current Unbrowser Local command plan:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py unbrowser-plan \
  --url https://gemini.google.com/app?hl=de \
  --prompt "Extract the visible provider state"
```

Run the current Unbrowser Local MCP stdio probe:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py unbrowser-mcp-probe \
  --url https://www.unbrowser.ai/ \
  --tool quick_fetch \
  --profile core \
  --artifact-root /tmp/hermes-unbrowser-mcp-probe \
  --output /tmp/hermes-unbrowser-mcp-probe.json
```

The probe starts `npx -y @unbrowser/local --profile=<profile>`, sends JSON-RPC initialize/tools calls over stdio, and writes `events.json` plus `status.json`. Use it for public-page extraction and Unbrowser capability checks. Keep paid provider workflows in `workflow-run`/`workflow-followup`, where browser profile, provider mode, account state, screenshots, and confirmation controls are recorded.

List model and tool catalogs:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py models
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py models --provider anthropic
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py models --provider google
```

The provider catalog should preserve common user aliases:

- `google` / `google-gemini` -> Gemini
- `anthropic` / `entropic` -> Claude
- `grog` / `xai` -> Grok

Keep provider model labels broad enough for the UI picker and exact enough for E2E assertions. Current examples include ChatGPT `GPT-5.5 Pro`, Gemini `Complex` / `Thinking with 3 Pro`, Perplexity `Sonar Deep Research`, and Grok `Grok 4.1 Fast Reasoning`.

Save the matrix for a later E2E run:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py matrix \
  --json \
  --output /tmp/ai-research-browser-matrix.json
```

Build the focused primary feature suite:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py feature-suite \
  --providers chatgpt,gemini,anthropic \
  --json \
  --output /tmp/hermes-ai-feature-suite-plan.json
```

Run Agent Browser against disposable profile clones:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py agent-browser-suite \
  --providers chatgpt,gemini,anthropic \
  --artifact-root /tmp/hermes-ai-research-agent-browser-e2e \
  --clone-root /tmp/hermes-ai-research-agent-browser-clones
```

Use `--plan-only` to inspect the queue first, `--max-runs 1` for a smoke test, and `--timeout 15` when a cloned browser is flaky. Treat `signed-out-or-wall` and `timeout` as real failed-login/automation-wall findings, not as success. For final account, plan, model, and quota proof, verify with a real running browser through Computer Use or a hidden CDP launch.

Before starting Gemini Deep Research or any paid workflow that must reuse the real account, run the real-session preflight:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py real-session-preflight \
  --browser brave \
  --profile work \
  --provider google \
  --output /tmp/hermes-real-session-preflight-brave-gemini.json
```

`real-session-preflight` reports `can_attach`, CDP endpoint attempts, port owner, running-browser blockers, and provider session evidence. If a disposable clone lands on a sign-in page while the real profile still has local provider session evidence, workflow runs are marked `real-session-required`. Do not claim Gemini Deep Research, ChatGPT Agent, or ChatGPT Deep Research started until a real CDP-enabled browser session or a dedicated minimized browser window confirms the provider UI state.

The profile alias `work` resolves by exact directory/name/account first, then by Work/Arbeit labels, and finally to the only discovered profile when a browser has exactly one local profile. This lets Comet/Komet single-profile setups such as `Neptune` run through `--profile work` without hard-coding a local-only directory name.

Run fixed provider workflows from a temporary profile clone:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-plan \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --mode agent \
  --prompt "Custom prompt" \
  --submit \
  --confirm-start
```

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-run \
  --browser brave \
  --profile work \
  --provider google \
  --mode deep-research \
  --prompt "Custom Deep Research prompt" \
  --submit \
  --confirm-start \
  --cache
```

Attach an image or file when the provider exposes a file input:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-run \
  --browser brave \
  --profile work \
  --provider google \
  --mode chat \
  --prompt "Analyze the attached image." \
  --attachment /tmp/example-image.png \
  --cache
```

Attachment upload uses CDP `DOM.setFileInputFiles` against the temporary clone only. The workflow first opens known upload menus such as Gemini's `Menü „Datei hochladen“ öffnen`; if the provider changes the menu or still hides the file input, the workflow records `no-file-input` for E2E evidence.

Run the focused workflow suite for the main agentic/research features:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-suite \
  --browsers brave \
  --profile work \
  --submit \
  --confirm-start \
  --continue-on-failure \
  --cache
```

The default suite covers ChatGPT Agent, ChatGPT Deep Research, Gemini Deep Research, Perplexity Research, Grok Research/DeepSearch, and Claude Research/Search. Use `--plan-only` before a long run, `--max-runs 1` for smoke tests, `--features provider:mode` for a hand-picked queue, and `--all-features` for every workflow mode implemented by the script.

`workflow-run` launches the real browser binary headless against a disposable copy of the selected profile, connects Agent Browser through CDP, selects the provider feature, fills the custom prompt, optionally confirms the provider start/research plan, writes screenshot/text/status artifacts, and terminates only the clone process. Confirmation must use exact visible controls; do not let generic labels such as `Start` match dictation, voice, or unrelated UI. If no exact start/research control or running marker appears, keep the status at `submitted`. Do not wire workflow automation to a live user browser window unless the user explicitly requests live mutation.

After a long Deep Research run has produced a chat URL, send a follow-up summary request and export/cache the current chat:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-followup \
  --browser brave \
  --profile work \
  --provider google \
  --chat-url https://gemini.google.com/app/example \
  --prompt "Fass den Deep-Research-Report kompakt zusammen." \
  --include-ai-exporter \
  --attachment /tmp/context-note.pdf \
  --cache \
  --export-markdown /tmp/gemini-followup.md
```

Use the interactive picker:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py wizard --headful
```

Preview a hidden background launch for one browser:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py launch-background \
  --browser opera \
  --profile Default \
  --provider google \
  --mode deep-research \
  --model "Thinking with 3 Pro" \
  --dry-run
```

Preview hidden background launches for every launchable browser:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py launch-all-background \
  --provider chatgpt \
  --mode agent \
  --model "GPT-5.5 Pro" \
  --dry-run
```

Remove `--dry-run` only when you actually want to start the background sessions. Use `--headless` for zero-window browser processes; otherwise the CLI uses hidden macOS app launches and an `osascript` hide guard.

Capture account/login/quota status from visible provider UI text:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py accounts \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --text-file /tmp/chatgpt-visible-text.txt
```

Build a local-only account/subscription audit across every discovered browser/profile/provider:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py account-audit \
  --output /tmp/ai-account-audit.json
```

`account-audit` reports `session_evidence` for ChatGPT, Gemini/Google, Claude/Anthropic, Grok/xAI, Perplexity, and OpenRouter. Treat `likely-logged-in` as a strong local session indicator, but still use `e2e-probe` or a visible UI capture for exact account email, subscription name, and remaining quota.

Parse already captured provider UI text files named `<browser>-<profile>-<provider>.txt`:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py account-audit \
  --text-dir /tmp/ai-provider-ui-text \
  --output /tmp/ai-account-audit.json
```

Treat `account-audit` JSON as private local evidence: it may contain names, emails, subscription labels, model names, and remaining Deep Research/Agent usage. Do not commit it.

List provider-specific probe hints:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py probe-specs
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py probe-specs --provider anthropic
```

Run a real Agent Browser/CDP E2E probe:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py e2e-probe \
  --artifact-root /tmp/hermes-ai-research-e2e \
  --browser chrome \
  --profile "Profile 2" \
  --provider chatgpt \
  --mode chat \
  --cdp-port 9224 \
  --open-controls
```

Parse a captured UI snapshot without touching a browser:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py e2e-probe \
  --artifact-root /tmp/hermes-ai-research-e2e \
  --browser opera \
  --profile Default \
  --provider anthropic \
  --mode chat \
  --text-file /tmp/opera-claude-visible-text.txt
```

Generate Oracle fetch/show commands:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py oracle-plan \
  -p "Review the provider E2E probes" \
  --file "skills/software-development/ai-research-browser/**" \
  --cdp-port 9224 \
  --deep-research
```

Parse visible existing chat names from a sidebar/list:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py parse-chats \
  --provider chatgpt \
  --text-file /tmp/chat-sidebar-visible-text.txt
```

Save a current conversation transcript into the cache:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py save-chat \
  --browser brave \
  --profile Default \
  --provider chatgpt \
  --chat-url https://chatgpt.com/c/example \
  --title "Existing research chat" \
  --text-file /tmp/chat-transcript.txt
```

Reuse cached chat data when available:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py chat-cache \
  --browser brave \
  --profile Default \
  --provider chatgpt \
  --chat-url https://chatgpt.com/c/example \
  --include-text
```

Force a fresh scrape/update:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py chat-cache \
  --browser brave \
  --profile Default \
  --provider chatgpt \
  --chat-url https://chatgpt.com/c/example \
  --text-file /tmp/fresh-chat-transcript.txt \
  --refresh
```

List the cache:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py list-chats
```

Check whether a browser/profile can be launched for CDP automation:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py preflight \
  --browser comet \
  --profile work
```

Build a hidden/headless launch command for ChatGPT Deep Research:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py launch-args \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --mode deep-research \
  --model GPT-5.5
```

Use `--headful` when you need to see the browser or when a provider blocks headless mode. Model selection is recorded in the launch plan as `model_selection: select-in-provider-ui`; a real E2E must verify the model picker visibly selected that model.

Verify captured UI text against expected mode markers:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py verify-text \
  --provider chatgpt \
  --mode deep-research \
  --text-file /tmp/chatgpt-visible-text.txt
```

Record an E2E result with a screenshot path:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py record-e2e \
  --artifact-root /tmp/hermes-ai-research-e2e \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --mode deep-research \
  --status verified \
  --screenshot /tmp/chatgpt-deep-research.png \
  --text-file /tmp/chatgpt-visible-text.txt \
  --note "Deep Research was selected in the ChatGPT tools menu."
```

## E2E Workflow

1. Run `discover` and choose an installed browser and profile.
2. Run `preflight` before attempting CDP/headless control.
3. If preflight is clean, launch with the generated `launch-args`; otherwise use Computer Use against the existing browser window.
4. Navigate to the provider:
   - ChatGPT: `https://chatgpt.com/`
   - Gemini: `https://gemini.google.com/app?hl=de`
   - Claude: `https://claude.ai/new`
   - Perplexity: `https://www.perplexity.ai/`
   - Grok: `https://grok.com/`
5. Select the requested mode in the provider UI.
6. Capture a real screenshot of the browser tab.
7. Extract visible UI text from Accessibility or the page.
8. Run `verify-text` and `record-e2e`.
9. Report whether the mode was truly started, only selected, blocked, or failed.

## Provider Notes

ChatGPT Deep Research is selected through the tools menu. A valid E2E needs to show the composer in Deep Research mode or a started research report.

ChatGPT Agent is selected through the tools menu or mode chip. A valid E2E needs to show the composer/task area in Agent mode or an active agent run.

Gemini Deep Research may be labeled `Deep Research`, `Recherche starten`, or `Start research` depending on locale and account state.

Gemini Agent availability varies by account and region. Record the visible account/model/quota text when it is shown.

Claude research and artifacts availability varies by account and current UI. A valid E2E should capture the visible mode marker, generated artifact panel, or sources/search state.

Grok may be typed as `grok` or `grog` in the CLI. Availability of research modes depends on the account and current Grok UI.

## Design Notes

This follows the same shape that makes Peter Steinberger's Peekaboo and Oracle useful for agents: separate discovery/snapshot JSON from actions, print a browser-control plan before touching a shared desktop, and avoid profile races by reusing reachable browser state or reporting blockers. The `matrix` command is the snapshot, while `wizard`, `launch-args`, `launch-background`, `launch-all-background`, `verify-text`, and `record-e2e` are the action/evidence layer.

If a user says "Oracle" in this context, check Peter Steinberger's `steipete/oracle` pattern first: API mode when possible, browser mode only with an explicit control plan, remote/reachable browser reuse, auto-reattach, Deep Research, and session artifacts. The CLI exposes Oracle as `oracle` for consult/code-review help and long-running session capture, and `oracle-plan` prints dry-run/status/session commands. It exposes OpenAI CUA as `openai-cua`, but keeps local logged-in browser profiles under `playwright-cdp`, `computer-use`, `agent-browser`, or `peekaboo`.

## Testing

Run unit tests from the repository root:

```bash
python3 -m unittest discover -s skills/software-development/ai-research-browser/tests -p 'test_*.py'
```
