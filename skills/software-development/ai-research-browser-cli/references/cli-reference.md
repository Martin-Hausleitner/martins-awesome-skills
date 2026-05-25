# AI Research Browser CLI Reference

This reference describes how to use `skills/software-development/ai-research-browser/scripts/ai_research_browser.py` safely and how to interpret its evidence.

## Mental Model

The CLI automates AI providers through installed browsers. Its safest real-E2E path is:

`discover -> real-session-preflight -> workflow-live-run -> status.json review -> optional suite/follow-up/export`

Use real live CDP whenever possible. `workflow-live-run` attaches to an already CDP-enabled browser, creates a separate automation target/tab, verifies the provider account and plan, submits only after guards pass, waits for output, writes artifacts, and can copy the final output to the macOS clipboard.

Use `workflow-run --strategy auto` when you want routing. Auto means real-session first. It must not silently use clone/sibling for real ChatGPT/Gemini E2E unless explicit fallback flags are supplied.

## Important Status Values

- `verified`: best success state. Login/guard passed, workflow produced an acceptable output.
- `captured`: output was captured, but the provider may not have hit a strong completion marker. Review output and screenshot.
- `started`: provider accepted a long-running workflow, but final output is not ready yet.
- `submitted`: prompt was sent, but no start/final proof yet.
- `blocked`: safety guard stopped the run. Review `blocker`, `pre_submit_guard.errors`, and screenshot.
- `timeout`: the CLI waited but did not prove completion. Inspect visible text, output, and screenshot.
- `rate-limited`: provider or guard detected quota/rate/challenge wall. Cooldown should be recorded.
- `signed-out-or-wall`: UI appears logged out or blocked by consent/security/login wall.
- `real-session-required`: local profile evidence exists, but UI proof failed; use a real live CDP session or manually seed sibling.

## Evidence Fields To Check

Always inspect:

- `status`
- `target_id` and `target_verification.automation_target_created`
- `pre_submit_guard.allowed`
- `pre_submit_guard.account`
- `pre_submit_guard.plan`
- `pre_submit_guard.model`
- `inventory.login_state`
- `output.text`
- `clipboard.copied`
- `rate_limit.detected`
- `screenshot`
- `real_session_preflight.cdp_owner_verification.ok`

Do not treat cookie evidence alone as logged-in proof.

## Discovery And Catalogs

Discover browsers and profiles:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py discover
```

List known providers, models, and tools:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py models
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py models --provider google
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py backends
```

Build a feature plan without executing:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py feature-suite \
  --providers chatgpt,gemini,anthropic,grok,perplexity \
  --json \
  --output /tmp/arb-feature-suite.json
```

## Real Session Preflight

Use this before any real E2E:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py real-session-preflight \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --port 9223 \
  --output /tmp/arb-preflight-brave-chatgpt.json
```

Expected success:

- `can_attach: true`
- `blockers: []`
- `cdp_owner_verification.ok: true`
- `owner_matches_browser: true`
- `user_data_dir_matches: true`
- `profile_directory_matches: true`

Example ports used in the recipes:

- Brave work-profile live CDP: `9223`
- Comet live CDP: commonly `9333`, or another verified port if configured locally
- Chrome: `9224`
- Opera: `9226`

Never assume port `9222` belongs to Brave/Chrome without owner verification.

Ambiguous Deep Research intent:

- If the user says only "Starte Deep Research" / "start Deep Research", route to
  Comet + Gemini Deep Research first.
- Use `--browser comet --profile work --provider google --mode deep-research
  --cdp-port 9333`.
- Run `real-session-preflight` before `workflow-run`.
- Do not submit until the user has supplied the real research prompt and
  `--allow-paid-quota-use` / confirmation are appropriate.

## Restart Recovery

Use restart recovery when the real browser/profile is running but no verified CDP is available.

Dry-run first:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py browser-cdp-recover \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --port 9223 \
  --dry-run \
  --output /tmp/arb-recover-plan.json
```

Execute only with explicit permission:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py browser-cdp-recover \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --port 9223 \
  --execute \
  --confirm-restart \
  --restore-focus original \
  --output /tmp/arb-recover-execute.json
```

Use `--include-full-tab-urls` only when raw tab URLs are acceptable. The default is redacted.

## Single Live Workflow

Safe low-cost ChatGPT smoke:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-live-run \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --mode chat \
  --cdp-port 9223 \
  --prompt "Reply with exactly: BRAVE_CHATGPT_SMOKE_E2E_OK" \
  --submit \
  --copy-output \
  --response-timeout 120 \
  --artifact-root /tmp/arb-chatgpt-smoke \
  --output /tmp/arb-chatgpt-smoke/status.json
```

Safe low-cost Gemini smoke:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-live-run \
  --browser brave \
  --profile work \
  --provider google \
  --mode chat \
  --cdp-port 9223 \
  --prompt "Reply with exactly: BRAVE_GEMINI_SMOKE_E2E_OK" \
  --submit \
  --copy-output \
  --response-timeout 120 \
  --artifact-root /tmp/arb-gemini-smoke \
  --output /tmp/arb-gemini-smoke/status.json
```

Paid Deep Research or Agent run:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-live-run \
  --browser brave \
  --profile work \
  --provider google \
  --mode deep-research \
  --cdp-port 9223 \
  --prompt-file /tmp/research-prompt.md \
  --submit \
  --confirm-start \
  --allow-paid-quota-use \
  --max-daily-paid-runs 1 \
  --copy-output \
  --response-timeout 1800 \
  --artifact-root /tmp/arb-gemini-deep \
  --output /tmp/arb-gemini-deep/status.json
```

Use `--attachment /absolute/path/file.png` or repeat `--attachment` for multiple files. If the provider exposes no file input, the run should record the failure instead of pretending upload worked.

## Strategy Router

Use `workflow-run` when you want the router:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-run \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --mode chat \
  --strategy auto \
  --cdp-port 9223 \
  --prompt "Reply with exactly: ROUTER_SMOKE_E2E_OK" \
  --submit \
  --copy-output \
  --output /tmp/arb-router-smoke.json
```

Strategy rules:

- `auto`: live CDP first; restart plan only when allowed; no silent clone/sibling for real E2E.
- `live-cdp`: require existing CDP.
- `restart-cdp`: plan or execute a real browser restart with CDP.
- `sibling`: explicit persistent sibling profile only.
- `diagnostic-clone`: explicit diagnostic clone only; never proof of real login.

To allow restart from `auto`, add `--allow-browser-restart`. To execute it, also add `--restart-execute --confirm-restart`.

## Workflow Suite

Plan a suite first:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-suite \
  --browsers brave \
  --profile work \
  --providers chatgpt,gemini \
  --features chatgpt:chat,gemini:chat \
  --plan-only \
  --output /tmp/arb-suite-plan.json
```

Run a small guarded suite. By default, `workflow-suite` uses temporary diagnostic
profile clones for matrix coverage; add `--sibling` for dedicated sibling
automation profiles. For real live-CDP E2E proof, use `workflow-run --strategy auto`
on one target at a time.

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-suite \
  --browsers brave \
  --profile work \
  --providers chatgpt,gemini \
  --features chatgpt:chat,gemini:chat \
  --submit \
  --copy-output \
  --require-login-state \
  --min-output-chars 20 \
  --rate-limit \
  --rate-limit-wait \
  --rate-limit-max-wait-seconds 300 \
  --rate-limit-fallback \
  --session-regression \
  --output /tmp/arb-suite-status.json
```

For paid workflows, add:

```bash
--allow-paid-quota-use --confirm-start --max-daily-paid-runs 1 --min-research-output-chars 1000
```

Do not run broad paid matrices until single-flow proof is stable.

## Rate Limit And CAPTCHA Behavior

The CLI should pause instead of retry-spamming when text indicates:

- CAPTCHA, reCAPTCHA, hCaptcha, Turnstile
- Cloudflare challenge or "Just a moment"
- "verify you are human"
- unusual traffic or automated traffic
- rate limit, usage limit, message limit, weekly/daily limit
- "please wait N minutes" or German equivalents

Use:

```bash
--rate-limit-state ~/.cache/ai-research-browser/rate-limit-state.json
```

When a challenge is detected, a conservative cooldown is recorded. `workflow-run`,
`workflow-live-run`, `workflow-sibling-run`, and `workflow-suite` all check that
state before starting provider UI work; active entries return `status=rate-limited`
with `pause_required` and `resume_after`. Use fallback only between verified
accounts:

```bash
--rate-limit-fallback --allow-rate-limit-fallback
```

Do not use CAPTCHA solvers, stealth plugins, fingerprint spoofing, or provider-defense bypasses.

## Privacy And Artifacts

Default:

```bash
--artifact-privacy redacted
```

Options:

- `redacted`: command logs and sensitive text redacted; recommended.
- `metadata-only`: minimal artifacts.
- `full`: raw command/output details; use only with explicit permission.

Do not commit screenshots, visible text files, raw chat outputs, cookie databases, or restart snapshots with private URLs.

## Sibling Profiles

Use sibling profiles only when explicitly requested or as setup/diagnostic fallback:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py sibling-profile-init \
  --browser comet \
  --profile work \
  --provider google \
  --sibling-user-data ~/.cache/ai-research-browser/sibling-profiles/comet-google/user-data
```

Then:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-sibling-run \
  --browser comet \
  --profile work \
  --provider google \
  --mode chat \
  --sibling-user-data ~/.cache/ai-research-browser/sibling-profiles/comet-google/user-data \
  --prompt "Reply with exactly: SIBLING_SMOKE_E2E_OK" \
  --submit \
  --copy-output \
  --output /tmp/arb-sibling-smoke.json
```

If Google/Gemini shows sign-in in a seeded sibling, treat it as `real-session-required`. The user must complete login/challenge inside that sibling profile.

## Cache, Follow-Up, And Export

Cache visible chat text:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-live-run \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --mode chat \
  --cdp-port 9223 \
  --prompt "Summarize this test." \
  --submit \
  --cache
```

List cached chats:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py list-chats \
  --provider chatgpt
```

Follow up in an existing chat:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-followup \
  --provider chatgpt \
  --chat-url "https://chatgpt.com/c/..." \
  --prompt "Fass zusammen" \
  --submit \
  --copy-output
```

`workflow-followup` is dry-run by default; `--submit` is required before it sends
the follow-up prompt. It also honors `--rate-limit-state` before opening provider
UI work.

Inspect SaveAI / AI Exporter:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py extensions --ai-exporter
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py ai-exporter-capabilities \
  --output /tmp/arb-ai-exporter-capabilities.json
```

Treat Notion sync as an external write; require explicit user permission.

## Troubleshooting

If `can_attach` is false:

1. Run `browser-cdp-recover --dry-run`.
2. If user allows restart, run `browser-cdp-recover --execute --confirm-restart`.
3. Re-run `real-session-preflight`.

If `signed-out-or-wall`:

1. Check screenshot and visible text.
2. Do not type.
3. Use the real browser/profile or manual sibling login.

If `timeout` but output exists:

1. Inspect `output.text`, `workflow_events[-1]`, and screenshot.
2. If the answer is present but not recognized, fix the waiter/parser before rerunning paid flows.

If `rate-limited`:

1. Check `rate_limit.entry.cooldown_until`.
2. Wait or switch only to another verified account.
3. Do not retry in a tight loop.

If a known account disappears:

1. Treat it as session regression.
2. Stop all prompt submission for that provider/profile.
3. Capture screenshot and status JSON.

## Quality Gate

After editing the CLI:

```bash
python3 -m py_compile skills/software-development/ai-research-browser/scripts/ai_research_browser.py
ruff check skills/software-development/ai-research-browser/scripts/ai_research_browser.py skills/software-development/ai-research-browser/tests/test_ai_research_browser.py
python3 -m unittest skills/software-development/ai-research-browser/tests/test_ai_research_browser.py
```

Then run one low-cost live smoke against a verified account before claiming real-provider stability.
