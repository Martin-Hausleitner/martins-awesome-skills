# AI Research Browser

Inventory and test AI providers across your installed browser profiles.

<p align="center">
  <img src="../../../assets/ai-research-browser-oracle-stack.svg" alt="AI Research Browser plus Oracle 0.13 architecture" width="920">
</p>

<p align="center">
  <img src="../../../assets/ai-research-browser-proof-cards.svg" alt="Sanitized proof cards for AI Research Browser Oracle integration" width="920">
</p>

This skill gives Hermes a local CLI for discovering installed Chromium-family browsers, finding their profiles, selecting a provider such as ChatGPT, Gemini, Claude, Perplexity, or Grok, and recording evidence for each tested AI feature.

It is designed for the real-world macOS setup where Brave, Comet/Komet, Chrome, and Edge may already be open with different accounts. The CLI does not blindly quit or relaunch those browsers; it reports blockers and lets you choose whether to run headful, headless, or via Computer Use.

Background runs are the default automation shape: the CLI can start launchable browsers through macOS `open -g -j` so the app is opened hidden and does not steal focus from the user. For zero-window runs, add `--headless`; for provider UIs that reject headless mode, keep the hidden background launch and verify via CDP, Computer Use, or Peekaboo.

## Oracle Integration

Oracle is integrated as a shared assist/runner layer inside the existing CLI, not as a separate sidecar that skips safety checks.

```mermaid
flowchart LR
  A["workflow-run"] --> B["Strategy router"]
  B --> C["Real CDP target"]
  B --> D["Restart plan"]
  C --> E["Local guards"]
  E --> F["Provider UI"]
  E --> G["Oracle 0.13 payload"]
  G --> H["status / reattach / show_session"]
  F --> I["status.json + screenshot evidence"]
  H --> I
```

The local CLI owns:

- browser/profile/CDP ownership verification
- login, account, plan, model, and feature evidence
- screenshot capture before typing
- paid-quota opt-in, pacing, rate-limit, CAPTCHA/challenge stop states
- ChatGPT model safety, including Pro/Extended Pro/GPT-5.5 Pro blocking

Oracle contributes:

- `@steipete/oracle@0.13.0` command construction
- browser attach via `--browser-attach-running --remote-chrome`
- long-run browser research flags such as `--browser-research deep`
- `status`, `reattach`, and `session --render` commands for long ChatGPT/Gemini jobs
- attachment wait support through `--browser-attachment-timeout`

The combined `workflow-run` payload includes both normal workflow state and Oracle evidence:

```json
{
  "selected_strategy": "live-cdp",
  "target_id": "automation-target",
  "pre_submit_guard": {"allowed": true},
  "oracle": {
    "mode": "assist",
    "reattach_available": true,
    "commands": {
      "status": ["npx", "-y", "@steipete/oracle@0.13.0", "status", "--hours", "72", "--browser-tabs"],
      "show_session": ["npx", "-y", "@steipete/oracle@0.13.0", "session", "<session-id>", "--render"]
    }
  }
}
```

If the local guards fail, `--oracle-mode runner` is marked `blocked-by-local-guards`; Oracle never becomes a bypass path.

## Quick Start

From the repository root:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py discover
```

Build the full browser x profile x provider x feature matrix:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py matrix --json \
  --backend playwright-cdp \
  --output /tmp/ai-research-browser-matrix.json
```

Build the focused paid-feature suite for the workflows that usually matter most:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py feature-suite \
  --providers chatgpt,gemini,anthropic \
  --json \
  --output /tmp/hermes-ai-feature-suite-plan.json
```

The focused suite checks:

- ChatGPT normal chat/model picker
- ChatGPT Deep Research
- ChatGPT Agent
- Gemini Deep Research
- Claude Opus
- Grok chat and DeepSearch/Research
- Perplexity chat and Research/Advanced Research

List installed SaveAI / AI Exporter extension copies:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py extensions --ai-exporter
```

The extension command reports browser/profile, extension id, version, popup, permissions, and manifest path. Use `--include-ai-exporter` on `workflow-run`, `workflow-suite`, or `workflow-followup` when a temporary profile clone should copy/load the SaveAI extension for export-oriented tests.

Inspect the reverse-engineered SaveAI / AI Exporter capabilities and Notion readiness:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py ai-exporter-capabilities \
  --output /tmp/hermes-ai-exporter-capabilities.json
```

This command parses the installed extension manifest and reports supported providers, available runtime actions such as `exportFullMarkdown`, `copyFullMarkdown`, `openFullNotionExport`, and `saveFullChatsToNotion`, plus local Notion session evidence without reading or emitting cookie values. Treat `saveFullChatsToNotion` as an external write: run Markdown export/cache first, then sync to Notion only when that write is intended.

Run Agent Browser against disposable browser-profile clones and write E2E artifacts:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py agent-browser-suite \
  --providers chatgpt,gemini,anthropic \
  --artifact-root /tmp/hermes-ai-research-agent-browser-e2e \
  --clone-root /tmp/hermes-ai-research-agent-browser-clones
```

Use `--plan-only` to see the complete queue first, `--max-runs 1` for a smoke test, and `--timeout 15` to keep flaky browser clones from hanging. The clone runner records `status.json`, `visible-text.txt`, and a screenshot for each probe. It reports automation walls such as ChatGPT `Just a moment...` as `signed-out-or-wall` even when the local profile contains session cookies, so clone success is not confused with a real usable login.

Run Agent Browser against a real CDP-enabled browser session and fail if the UI is not actually logged in:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py agent-browser-live-suite \
  --providers chatgpt,claude,grok,perplexity \
  --browsers brave \
  --profile Work \
  --cdp-port 9223 \
  --assert-login \
  --artifact-root /tmp/hermes-ai-research-agent-browser-live
```

This is the "truth" path for Agent Browser. The target browser must already be running with `--remote-debugging-port=<port>` against the intended profile. The examples use a Brave work profile on port `9223`; do not assume any port belongs to Brave unless `real-session-preflight` verifies the port owner. If Agent Browser auto-connects to a signed-out clone or a different Chromium instance, the live suite records `signed-out-or-wall` and exits non-zero instead of treating the capture as usable.

Before starting Gemini Deep Research or any paid workflow that must reuse the real account, run the real-session preflight:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py real-session-preflight \
  --browser brave \
  --profile work \
  --provider google \
  --output /tmp/hermes-real-session-preflight-brave-gemini.json
```

`real-session-preflight` checks whether the intended browser/profile has a reachable CDP endpoint, whether the default port is occupied by another process, whether the browser is already running without `--remote-debugging-port`, and whether local site data shows provider session evidence. If a clone run lands on a sign-in page while session evidence exists, workflow results are marked `real-session-required`; final Gemini Deep Research E2E needs a real CDP-enabled session or a dedicated minimized sibling automation profile, not a disposable clone.

Recover a real browser into a CDP-enabled session only after an explicit approval step:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py browser-cdp-recover \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --dry-run \
  --output /tmp/hermes-brave-cdp-recover-plan.json
```

`browser-cdp-recover` is dry-run unless `--execute` is passed. The execute path snapshots current browser windows/tabs to `~/.cache/ai-research-browser/recovery/`, shows a macOS confirmation dialog when `--confirm-restart` is used, gracefully quits the browser, restarts it with `--remote-debugging-address=127.0.0.1` and `--remote-debugging-port=<port>`, requests session restore, verifies CDP, and records restore/focus metadata. Snapshot artifacts are redacted by default and store domains, not full tab URLs; `--include-full-tab-urls` is an explicit diagnostic opt-in.

Run the safer strategy-routed workflow entrypoint:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-run \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --mode chat \
  --strategy auto \
  --cdp-port 9223 \
  --artifact-privacy redacted \
  --prompt "Say READY in one short sentence." \
  --submit \
  --copy-output \
  --output /tmp/hermes-chatgpt-live.json
```

`workflow-run --strategy auto` now prefers a real attachable CDP session and can return a `restart-cdp` recovery plan when `--allow-browser-restart` is set. It does not silently fall back to sibling or clone profiles; use `--allow-sibling-fallback`, `--strategy sibling`, or `--strategy diagnostic-clone` only when that is intentionally the test target. Clone results are marked as not eligible for real account baselines even if copied cookies appear signed in. Each result includes `strategy`, `selected_strategy`, `target_id`, `target_verification`, `cdp_owner_verification`, `privacy`, `pre_submit_guard`, `pacing`, `rate_limit_budget`, `account_baseline`, and restart/restore fields when applicable.

Hardening defaults are conservative: command logs are redacted unless `--artifact-privacy full` is used, paid/quota-spending modes require `--allow-paid-quota-use`, pacing defaults to `conservative`, and live workflows require a dedicated automation target instead of falling back to the active tab. `--allow-active-tab-navigation-dangerously` remains a diagnostic escape hatch only. “Humanize” means slower compliant pacing and lower request pressure; the CLI does not use stealth plugins, fingerprint spoofing, CAPTCHA solving, or provider-defense bypasses.

Run a sibling automation session without touching already-open Brave/Comet windows:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-sibling-run \
  --browser comet \
  --profile work \
  --provider google \
  --mode deep-research \
  --prompt "Custom Deep Research prompt" \
  --submit \
  --confirm-start \
  --cache \
  --output /tmp/hermes-gemini-sibling.json
```

`workflow-sibling-run` creates or reuses a separate `--user-data-dir` under `~/.cache/ai-research-browser/sibling-profiles/<browser-profile>/user-data`, starts the real browser binary headful but offscreen with a fresh CDP port, opens only the automation page, and never launches the source profile directory while the user's visible browser is running. Use `--sibling-user-data <dir>` for a named persistent automation profile, `--refresh-sibling` to re-seed it from the source profile, and `--close-after` for smoke tests. A provider may still reject a hot-cloned session: in a real Comet/Gemini smoke, Google accepted consent and loaded Gemini, but displayed `Anmelden`, so that run was correctly recorded as `signed-out-or-wall` rather than success. For production, seed a dedicated sibling profile once, log into the required providers there, and then reuse it for background E2E workflows.

Initialize that dedicated sibling profile with a visible one-time login window:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py sibling-profile-init \
  --browser comet \
  --profile work \
  --provider google \
  --sibling-user-data ~/.cache/ai-research-browser/sibling-profiles/comet-google/user-data
```

`sibling-profile-init` intentionally opens the automation profile visibly so the provider can bind its session to that persistent browser profile/device state. After manual login, future `workflow-sibling-run` calls can reuse the same `--sibling-user-data` offscreen. This avoids relying on copied cookies alone, which modern providers can reject through device-bound session credentials or server-side anomaly checks.

The profile alias `work` resolves by exact directory/name/account first, then by Work/Arbeit labels, and finally to the only discovered profile when a browser has exactly one local profile. This keeps single-profile Comet/Komet setups usable through `--profile work` without hard-coding a machine-specific directory name.

Fill a provider composer and export the visible transcript/output through the same real CDP session:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py agent-browser-ask \
  --provider perplexity \
  --browser brave \
  --profile Work \
  --cdp-port 9223 \
  --prompt "Say READY in one short sentence." \
  --submit \
  --cache \
  --artifact-root /tmp/hermes-ai-research-agent-browser-ask
```

Omit `--submit` for a non-spending dry run that fills the composer and exports the current UI text. With `--cache`, the captured text is saved into the local chat cache for reuse or deliberate refresh.

Run the full local orchestration for a provider feature: real-session preflight, optional Unbrowser Local MCP proof, SaveAI / AI Exporter capability scan, Agent Browser workflow, optional "Fass zusammen" follow-up, and a Notion export eligibility plan:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-orchestrate \
  --browser brave \
  --profile work \
  --provider google \
  --mode deep-research \
  --prompt "Custom Deep Research prompt" \
  --unbrowser \
  --unbrowser-session \
  --include-ai-exporter \
  --followup \
  --notion-sync \
  --output /tmp/hermes-gemini-orchestrate.json
```

`workflow-orchestrate` does not quit or relaunch existing browsers. It records the exact blocker when the real session is not CDP-attachable, still runs the safe clone workflow for selector/upload evidence, can query Unbrowser's saved session state, and marks the Notion step as ineligible unless `--allow-external-write` is set and an exportable output exists. This keeps AI Exporter / Notion writes explicit while still showing whether the installed extension and Notion session are ready.

Use the interactive picker:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py wizard --headful
```

The wizard prints pure JSON to stdout, so it can be piped into other scripts.

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

Preview background launches for every launchable discovered browser:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py launch-all-background \
  --provider chatgpt \
  --mode agent \
  --model "GPT-5.5 Pro" \
  --dry-run
```

Remove `--dry-run` to actually start the background sessions. If a browser is already running without `--remote-debugging-port`, the CLI reports blockers instead of racing a second instance against the same profile. Use `--force` only when you intentionally accept that risk.

## Providers

Current provider registry:

- ChatGPT: `chat`, `deep-research`, `agent`
- Gemini: `chat`, `deep-research`, `agent`
- Claude: `chat`, `research`, `artifacts`
- Perplexity: `chat`, `research`
- Grok: `chat`, `research`
- OpenRouter: `chat`, `models`, `credits`

`grog` and `xai` are accepted aliases for `grok`.

## Browser Support

The CLI currently discovers:

- Brave Browser
- Comet/Komet
- Google Chrome
- Microsoft Edge
- Opera
- ChatGPT Atlas

Profiles are read from Chromium `Local State` and `Preferences`, including display name and account email when Chromium exposes it. Some browsers, notably Opera, hide the account identifier even when sync/session state exists; those profiles are marked with `account_state: signed-in-hidden`.

Discovery also reports `app_exists`, `binary_exists`, and `user_data_exists`. This matters on machines where stale profile data remains after an app was removed: the browser may be discoverable for cache/profile inspection but not launchable until the app binary exists again.

## Models and Tools

List selectable provider models and tools:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py models
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py models --provider anthropic
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py models --provider google
```

Provider aliases include `google`/`google-gemini` for Gemini, `anthropic`/`entropic` for Claude, and `grog`/`xai` for Grok. The catalog includes provider/source URLs and current UI/API labels such as ChatGPT `GPT-5.5 Pro`, Gemini `Complex` / `Thinking with 3 Pro`, Perplexity `Sonar Deep Research`, and Grok `Grok 4.1 Fast Reasoning`. Launch plans can carry the intended model, but the CLI does not fake model selection through URL parameters; it records `model_selection: select-in-provider-ui` so the E2E step must verify the visible provider UI.

## Account and Quota Capture

Profile metadata alone does not always reveal which provider account is logged in. For provider-specific account and quota status, capture visible UI text from a real tab and pass it to:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py accounts \
  --browser brave \
  --profile Default \
  --provider chatgpt \
  --text-file /tmp/provider-visible-text.txt
```

The parser extracts:

- provider account email, when visible
- selected model, when visible as `Model: ...`
- plan/subscription labels such as ChatGPT Pro, Gemini Advanced, Claude Max, Perplexity Pro, or SuperGrok, when visible
- Deep Research remaining count, when visible
- Agent task remaining count, when visible
- usage snippets such as `75% used`, `3/3 left`, and reset hints such as `resets tomorrow`

Build a full account/subscription audit inventory across every discovered browser/profile/provider:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py account-audit \
  --output /tmp/ai-account-audit.json
```

`account-audit` also scans local browser profile site data for provider session evidence. It reports matching cookie names, hosts, and IndexedDB origins, but never reads or emits cookie values. This is how the audit distinguishes "profile account hidden" from "provider session likely logged in" for sites such as ChatGPT, Gemini/Google, Claude, Grok, Perplexity, and OpenRouter.

If you have provider UI text captures, put them in a local-only directory as `<browser>-<profile>-<provider>.txt` and let the audit parse them:

```bash
mkdir -p /tmp/ai-provider-ui-text
# Example: /tmp/ai-provider-ui-text/brave-default-chatgpt.txt
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py account-audit \
  --text-dir /tmp/ai-provider-ui-text \
  --output /tmp/ai-account-audit.json
```

Rows with parsed provider text are marked `captured`. Rows without UI text but with local session-cookie/storage evidence are marked `session-detected-needs-ui-capture`; rows without either are marked `needs-ui-capture`. Their `background_plan` contains the hidden/headless launch command needed to collect the provider page without distracting the user. Keep the resulting JSON local because it may contain private names, emails, subscription labels, and usage quotas.

Inspect supported automation backends:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py backends
```

The local-first path is `playwright-cdp` for deterministic browser control plus `computer-use` or `peekaboo` for screenshot-backed proof. Peter Steinberger's `@steipete/oracle` is represented as `oracle`: use it for multi-model code review, consults, browser-session reattach, and session artifacts. It is not a replacement for auditing subscriptions inside your own local browser profiles. `unbrowser-local` represents `@unbrowser/local`; use it for extraction and pattern-learning checks around pages, while provider UI actions that spend quota or start Deep Research stay in the CDP workflow so screenshots and mode/account verification remain explicit. Managed alternatives such as OpenAI CUA/Operator, Claude Computer Use, Gemini Computer Use, Stagehand, Browser-Use, and Hyperbrowser are represented as comparison backends, not as replacements for your local logged-in profiles.

Generate an Unbrowser command plan:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py unbrowser-plan \
  --url https://gemini.google.com/app?hl=de \
  --prompt "Extract visible provider state" \
  --output-path /tmp/unbrowser-gemini.json
```

The current Unbrowser site points at `npx @unbrowser/local` for the local runner, and the local package behaves as an MCP stdio server. Use `unbrowser-mcp-probe` to initialize the server, list the advertised tools, and optionally call `quick_fetch`, `smart_browse`, or `research` with JSON-RPC:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py unbrowser-mcp-probe \
  --url https://www.unbrowser.ai/ \
  --tool quick_fetch \
  --profile core \
  --artifact-root /tmp/hermes-unbrowser-mcp-probe \
  --output /tmp/hermes-unbrowser-mcp-probe.json
```

The probe writes `events.json` and `status.json` under the artifact root. It is meant for public-page extraction and pattern-learning checks; provider UI actions that start paid Deep Research or Agent runs stay in the CDP workflow where mode, account state, and screenshots are recorded explicitly.

Check Unbrowser Local saved sessions without touching provider UI:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py unbrowser-session \
  --action health \
  --domain gemini.google.com \
  --session-profile default \
  --output /tmp/hermes-unbrowser-gemini-session.json
```

The session command wraps Unbrowser's MCP `session_management` tool for `list` and `health`. It is useful evidence for authenticated-content readiness, but it does not replace the real browser CDP proof required before spending Deep Research or Agent quota.

Show provider-specific probe hints before writing or running selectors:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py probe-specs
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py probe-specs --provider anthropic
```

Run a real provider probe through Agent Browser against a CDP-enabled browser:

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

`e2e-probe` opens the provider URL, captures an Agent Browser accessibility snapshot, optionally opens known model/tool controls, takes a screenshot, and writes `status.json` plus `visible-text.txt`. The inventory includes inferred login state, visible account/email, plan, selected model, matched model/tool labels, available mode markers, and usage/limit lines.

Use `agent-browser-live-suite` for a whole focused suite against the real CDP session. Unlike `e2e-probe`, it can assert that each result is logged in:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py agent-browser-live-suite \
  --providers chatgpt,claude,grok,perplexity \
  --browsers brave \
  --profile Work \
  --cdp-port 9223 \
  --assert-login \
  --max-runs 8
```

Use `agent-browser-ask` when the goal is not just inventory but controlling the provider and exporting visible output. It opens the provider URL, verifies the page is not a sign-in/wall state, fills the composer, optionally submits, waits, snapshots again, saves a screenshot, and can write the visible text to the chat cache.

For non-CDP browsers, `agent-browser-suite` creates a disposable clone of the selected Chromium profile and launches Agent Browser with `--profile <clone-user-data>` plus the browser executable. This is useful as a repeatable E2E smoke test, but it is intentionally conservative: if provider cookies are present yet the cloned/headless browser lands on a sign-in or anti-automation page, the result is recorded as `signed-out-or-wall`. Use a real running browser plus Computer Use or a CDP-enabled hidden launch for final account, plan, model, and quota proof.

Use `workflow-run` for the fixed "select feature -> send custom prompt -> confirm start -> extract output" path. In `auto` mode it uses only a verified real CDP session or an explicit restart-recovery plan; it blocks rather than launching sibling/clone profiles. Use `workflow-sibling-run` or `--strategy diagnostic-clone` only for intentional non-real-session diagnostics.

Use `workflow-sibling-run` for the same fixed path when the provider needs a persistent, authenticated automation profile instead of a disposable clone. It launches the real browser binary offscreen/headful against a separate sibling `--user-data-dir`, cleans only stale locks inside that sibling directory, and terminates only the launched sibling process when `--close-after` is set:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-sibling-run \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --mode deep-research \
  --prompt "Custom Deep Research prompt" \
  --submit \
  --confirm-start \
  --include-ai-exporter \
  --cache
```

For the first setup of a fresh sibling profile, omit `--submit` and `--close-after`, then authenticate the provider in that dedicated automation profile. Subsequent runs reuse the same profile and can run in the background without touching the user's active browser windows.

If `workflow-sibling-run` sees local provider session evidence but the visible UI still shows a sign-in wall, it returns `real-session-required`. That status means the sibling profile exists but needs a real manual login or provider challenge resolution; it is not a successful Deep Research/Agent start.

Preview the exact safe plan:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-plan \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --mode agent \
  --prompt "Open a test chat and summarize the account-visible feature state." \
  --submit \
  --confirm-start
```

Start ChatGPT Deep Research or ChatGPT Agent:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-run \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --mode deep-research \
  --prompt "Research the latest public docs for OpenAI Deep Research and produce a concise source-backed summary." \
  --submit \
  --confirm-start \
  --cache \
  --output /tmp/chatgpt-deep-research-workflow.json
```

Start Gemini Deep Research:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-run \
  --browser brave \
  --profile work \
  --provider google \
  --mode deep-research \
  --prompt "Use Deep Research to compare current browser automation options for logged-in AI accounts." \
  --submit \
  --confirm-start \
  --output /tmp/gemini-deep-research-workflow.json
```

Attach an image or file to a provider composer when a visible file input exists:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-run \
  --browser brave \
  --profile work \
  --provider google \
  --mode chat \
  --prompt "Analyze the attached image and summarize what matters." \
  --attachment /tmp/example-image.png \
  --output /tmp/gemini-image-chat-workflow.json
```

Attachment upload is intentionally evidence-driven: the workflow first tries provider-specific upload-menu labels such as Gemini's `Menü „Datei hochladen“ öffnen`, then records an `attach-files` event with `ok: true`, `no-file-input`, or an error. If a provider changes the upload menu, use Agent Browser snapshots to discover the exact label before relying on automated file upload.

Start Perplexity Research or Grok DeepSearch:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-run \
  --browser brave \
  --profile work \
  --provider perplexity \
  --mode research \
  --prompt "Research the topic and return citations plus a short conclusion." \
  --submit \
  --confirm-start
```

Run the focused workflow suite for the main paid/agentic features in one command:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-suite \
  --browsers brave \
  --profile work \
  --submit \
  --confirm-start \
  --continue-on-failure \
  --cache \
  --output /tmp/hermes-ai-workflow-suite.json
```

By default the suite covers ChatGPT Agent, ChatGPT Deep Research, Gemini Deep Research, Perplexity Research, Grok Research/DeepSearch, and Claude Research/Search. Use `--features chatgpt:agent,gemini:deep-research`, `--providers chatgpt,gemini`, `--max-runs 1`, or `--plan-only` to narrow or preview the queue. Use `--all-features` when you want every workflow mode implemented by `workflow-run`.

Each workflow writes `status.json`, `visible-text.txt`, `output.txt`, and a screenshot under the artifact root. The JSON records the clicked feature trigger, confirmation trigger, current URL, extracted output text, account inventory, and cache metadata when `--cache` is set. Confirmation clicks are exact-control only, so generic labels such as `Start` cannot accidentally hit dictation or voice controls; if a provider keeps the feature chip selected but never renders an exact research/agent start control, the run remains `submitted` instead of being reported as started.

For Gemini specifically, a profile clone can show `likely-logged-in` cookie evidence but still load a Google sign-in/consent wall. That is intentionally not treated as success. Use `real-session-preflight` and the hidden Gemini commands in its output before claiming Deep Research has started.

When a real browser was already started intentionally with `--remote-debugging-port`, use the live workflow path. It opens a new Agent Browser-controlled tab in that CDP session, leaves existing tabs alone, leaves the automation tab open for long-running research, and writes the same artifacts as the clone workflow:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-live-run \
  --browser brave \
  --profile work \
  --provider google \
  --mode deep-research \
  --cdp-port 9223 \
  --prompt "Use Gemini Deep Research for this custom prompt." \
  --submit \
  --confirm-start \
  --cache \
  --output /tmp/gemini-live-deep-research.json
```

The live command blocks before touching the provider UI when preflight cannot attach to the requested CDP port. `workflow-orchestrate --live-cdp --port <port>` uses the same live path while also checking Unbrowser sessions, AI Exporter capabilities, follow-up eligibility, and Notion export readiness.

Send a follow-up prompt into an existing provider chat, then export/cache the refreshed transcript:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-followup \
  --browser brave \
  --profile work \
  --provider google \
  --chat-url https://gemini.google.com/app/example \
  --prompt "Fass den bisherigen Deep-Research-Report kompakt zusammen und nenne die wichtigsten Quellen." \
  --include-ai-exporter \
  --attachment /tmp/context-note.pdf \
  --cache \
  --export-markdown /tmp/gemini-followup.md \
  --output /tmp/gemini-followup.json
```

`workflow-followup` uses the same disposable profile-clone CDP shape as `workflow-run`: it does not close or mutate existing user browser windows, sends the follow-up only when `--no-submit` is not set, records screenshot/text/status artifacts, writes a Markdown export, and refreshes the local chat cache when `--cache` is enabled. This is the intended second phase after a long Gemini or ChatGPT Deep Research run: wait for the research chat URL to finish, send "fass zusammen", optionally attach a file, then copy/export the final state.

When you already have visible UI text from Computer Use, Peekaboo, or another capture, parse it without touching the browser:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py e2e-probe \
  --artifact-root /tmp/hermes-ai-research-e2e \
  --browser opera \
  --profile Default \
  --provider anthropic \
  --mode chat \
  --text-file /tmp/opera-claude-visible-text.txt
```

Generate concrete Oracle fetch/show commands for a second-model consult:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py oracle-plan \
  -p "Review the AI provider E2E probes" \
  --file "skills/software-development/ai-research-browser/**" \
  --cdp-port 9224 \
  --deep-research
```

## Existing Chat Cache

Existing chats can be archived and reused across later test runs. This lets Hermes continue from a known conversation snapshot instead of scraping the same UI again every time.

Parse a visible chat sidebar/listing:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py parse-chats \
  --provider chatgpt \
  --text-file /tmp/chat-sidebar-visible-text.txt
```

Save a chat transcript into the local cache:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py save-chat \
  --browser brave \
  --profile Default \
  --provider chatgpt \
  --chat-url https://chatgpt.com/c/example \
  --title "Preisvergleich Original vs Angebote" \
  --text-file /tmp/chat-transcript.txt
```

Read from cache when present, otherwise report that a scrape is needed:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py chat-cache \
  --browser brave \
  --profile Default \
  --provider chatgpt \
  --chat-url https://chatgpt.com/c/example \
  --include-text
```

Force a fresh scrape/update with `--refresh`:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py chat-cache \
  --browser brave \
  --profile Default \
  --provider chatgpt \
  --chat-url https://chatgpt.com/c/example \
  --text-file /tmp/fresh-chat-transcript.txt \
  --refresh
```

List cached chats:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py list-chats
```

Default cache root is `~/.cache/ai-research-browser/chats`. Override it with `--cache-root` or `AI_RESEARCH_BROWSER_CACHE`.

## Launch Args

Generate a command for a selected profile/provider/feature:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py launch-args \
  --browser brave \
  --profile Default \
  --provider grok \
  --model "Grok 4.20 Expert" \
  --mode research \
  --headful
```

Without `--headful`, the generated command includes `--headless=new`.

## Background Launch

`launch-background` and `launch-all-background` are the preferred commands for unattended AI-provider control on a shared desktop. They produce a structured plan and, unless `--dry-run` is set, start the browser with:

- `/usr/bin/open -g -j -n -a <Browser.app>` so macOS does not activate the app
- `--remote-debugging-port=<port>` for CDP control
- `--user-data-dir=<profile root>` and `--profile-directory=<profile>` for the chosen account/profile
- an `osascript` post-launch hide command as a second guardrail

The launch plan records `model_selection: select-in-provider-ui`; the automation must still verify the model/mode inside the provider UI before claiming a Deep Research or Agent run has started.

## Preflight

Before a hidden/CDP run, check whether the browser is already running in a way that blocks automation:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py preflight \
  --browser comet \
  --profile Default
```

If a port is already used or the browser is already running without `--remote-debugging-port`, the CLI reports that instead of doing anything destructive.

## E2E Evidence

Record a tested run:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py record-e2e \
  --artifact-root /tmp/hermes-ai-research-e2e \
  --browser brave \
  --profile Default \
  --provider gemini \
  --mode deep-research \
  --status verified \
  --screenshot /tmp/gemini-research.png \
  --text-file /tmp/gemini-visible-text.txt \
  --note "Gemini showed Researching websites."
```

The record includes the provider, feature, browser/profile, screenshot path, verification markers, account/model/quota hints, and notes.

## Design Inspiration

This follows the pattern that makes Peter Steinberger's Peekaboo and Oracle useful for agents: keep discovery/snapshot data as structured JSON, print the browser-control plan before touching a shared desktop, then run actions and verification against that state. The CLI therefore separates:

- `discover` and `matrix`: inventory/snapshot
- `preflight`: blocker detection
- `wizard`, `launch-args`, `launch-background`, and `launch-all-background`: selected action plan
- `verify-text` and `record-e2e`: evidence capture

Peter Steinberger's Oracle is a separate multi-model consult CLI; its browser-mode lesson for this skill is to reuse/reattach to a reachable browser, keep session artifacts, and avoid surprising shared desktops. This CLI mirrors that locally by offering dry-run plans, hidden macOS launches, CDP ports, and blocker reporting before execution. When Oracle is installed, use it alongside this CLI for coding help or long-running model consultation; use this CLI for browser/profile/provider/account inventory.

## Tests

```bash
python3 -m unittest discover -s skills/software-development/ai-research-browser/tests -p 'test_*.py'
```
