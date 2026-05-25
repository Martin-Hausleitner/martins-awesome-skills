---
name: ai-research-browser-cli
description: Use when running, debugging, or explaining the ai-research-browser CLI for real Browser/CDP AI-provider automation, including Brave/Comet live sessions, restart recovery, workflow-live-run, workflow-suite, Deep Research/Agent/image runs, rate-limit cooldowns, screenshots, clipboard output, and safe E2E evidence.
version: 0.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [ai-research-browser, cli, browser-automation, cdp, brave, comet, chatgpt, gemini, e2e]
    related_skills: [ai-research-browser, browser-profile-routing, agent-browser-macos-profile-testing, ai-research-ui-fallbacks]
---

# AI Research Browser CLI

Use this skill when the user wants to operate the `ai_research_browser.py` CLI, verify real logged-in AI-provider sessions, run E2E workflows, or understand which command/flag to use.

CLI path:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py
```

## Operating Rules

- Prefer real live CDP sessions for true E2E. The examples use a Brave work profile on port `9223`; always verify the CDP owner/profile instead of trusting a port number.
- If the user only says "Starte Deep Research" / "start Deep Research" and does not name a browser or provider, default to Comet + Gemini Deep Research: `--browser comet --profile work --provider google --mode deep-research --cdp-port 9333`, with preflight first and no `--submit` until the actual research prompt and quota permission are explicit.
- Never claim a provider works until the status JSON proves login/account/plan, an automation `target_id`, screenshot evidence, output text, and no challenge/rate-limit wall.
- Do not use temporary clone/sibling success as proof of a real account login. Clone/sibling runs are diagnostic or explicit fallback only.
- Before typing or submitting, require provider inventory: signed-in state, visible account, plan, model/feature evidence, screenshot, and no CAPTCHA/rate-limit/challenge.
- Paid/quota workflows such as Deep Research, Agent, image generation, research, artifacts, or Labs need `--allow-paid-quota-use`.
- Deep Research prompts must pass the prompt-budget guard before submit: ideal `<= 6,000` chars, default automated max `<= 12,000` chars, review required above that, and block above `24,000` chars. See `docs/DEEP_RESEARCH_PROMPT_BUDGETS.md`.
- If CAPTCHA, Cloudflare, Turnstile, login challenge, provider warning, or rate-limit text appears, stop and persist cooldown. Do not solve or bypass it.
- For restart recovery, generate a dry-run plan first. Execute restart only when the user explicitly allowed it or supplied the required restart flags.
- Use `--artifact-privacy redacted` by default. Use `full` only when the user explicitly needs raw URLs/text and accepts the privacy tradeoff.
- After implementation or changes, run syntax, lint, unit tests, and at least one low-cost real provider smoke before saying the CLI is stable.

## Fast Workflow

For the ambiguous one-line prompt "Starte Deep Research", do not route to a
Brave-first fallback or a broad matrix. Start with the Comet/Gemini preflight:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py real-session-preflight \
  --browser comet \
  --profile work \
  --provider google \
  --port 9333 \
  --output /tmp/arb-preflight-comet-gemini.json
```

Only after the preflight proves the real account, plan, feature, screenshot, and
CDP target should a paid Deep Research run be planned or submitted.

Before submitting a real Deep Research prompt, measure it:

```bash
python3 skills/research/comparison-deep-research/scripts/deep_research_prompt_budget.py \
  --file /tmp/deep-research-prompt.txt \
  --json
```

1. Discover browsers/profiles:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py discover
```

2. Verify the real CDP owner and provider session:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py real-session-preflight \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --port 9223 \
  --output /tmp/arb-preflight.json
```

3. Run a low-cost live smoke and copy the verified output:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py workflow-live-run \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --mode chat \
  --cdp-port 9223 \
  --prompt "Reply with exactly: CLI_SMOKE_E2E_OK" \
  --submit \
  --copy-output \
  --response-timeout 120 \
  --output /tmp/arb-live-smoke.json
```

4. Inspect the result. Treat only `verified` or a clearly successful `captured` result with output as success.

5. For Deep Research/Agent/image runs, add:

```bash
--allow-paid-quota-use --confirm-start --max-daily-paid-runs 1
```

## Command Reference

For complete command recipes, status interpretation, recovery flows, and E2E checklists, read [references/cli-reference.md](references/cli-reference.md).

Load the reference when:

- the user asks how to use any CLI subcommand;
- a run hits `blocked`, `timeout`, `real-session-required`, `signed-out-or-wall`, or `rate-limited`;
- you need examples for restart recovery, workflow suites, attachments, cache/follow-up, AI Exporter, or provider-specific modes.

## Validation

Before reporting completion after a code or skill change:

```bash
python3 -m py_compile skills/software-development/ai-research-browser/scripts/ai_research_browser.py
ruff check skills/software-development/ai-research-browser/scripts/ai_research_browser.py skills/software-development/ai-research-browser/tests/test_ai_research_browser.py
python3 -m unittest skills/software-development/ai-research-browser/tests/test_ai_research_browser.py
```

For real E2E, start with one low-cost `workflow-live-run` against a verified account. Do not launch a broad paid matrix until single-flow evidence is green.
