---
name: oracle-ai-research-e2e
description: Use when validating Oracle 0.13 with ai-research-browser, workflow-run, GitHub public-safe proof, local Hermes skill installation, guarded ChatGPT/Gemini browser E2E, or reattach/status/session evidence.
version: 0.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [oracle, ai-research-browser, e2e, github, hermes, browser-automation]
    related_skills: [ai-research-browser, ai-research-browser-cli]
---

# Oracle AI Research E2E

Use this skill to prove that Peter Steinberger's Oracle 0.13 layer and the local `ai-research-browser` CLI work together, without turning Oracle into a bypass for account, plan, model, quota, or screenshot guards.

The public-safe local harness is:

```bash
python3 skills/software-development/oracle-ai-research-e2e/scripts/oracle_ai_research_e2e_check.py
```

## What To Prove

Check all of these before claiming the integration works:

- `@steipete/oracle@0.13.0` appears in generated commands.
- `oracle-plan` emits `--browser-attach-running`, `--remote-chrome`, `--browser-research`, `status`, `reattach`, and `session --render`.
- `workflow-run --oracle-mode assist|runner` writes Oracle evidence into the same workflow payload.
- `runner` mode blocks when local login/account/plan/feature/screenshot guards fail.
- ChatGPT Pro/Extended Pro/GPT-5.5 Pro are blocked before UI typing.
- Slash feature fallback does not type into the composer before the pre-submit guard.
- Public GitHub artifacts are sanitized; no real cookies, tokens, user paths, prompts, or private screenshots are committed.

## Safe Default Check

From the repo root:

```bash
python3 skills/software-development/oracle-ai-research-e2e/scripts/oracle_ai_research_e2e_check.py \
  --json
```

This runs only local, public-safe checks:

- syntax compile of `ai_research_browser.py`
- Oracle-focused unit tests
- ChatGPT model-safety and slash-guard regression tests
- `oracle-plan` command generation
- `workflow-run --oracle-mode runner` blocked-path proof
- `oracle-e2e-smoke` opt-in blocking proof
- public-safety audit

On Linux CI hosts without Brave/Comet/Chrome profiles, the browser-dependent `workflow-run` runner proof is reported as `skipped: browser-not-discovered-on-this-host`; on the local macOS Hermes machine it should run and prove `blocked-by-local-guards`.

## Real Provider E2E

Run real E2E only when the browser CDP session and paid-quota use are intentional:

```bash
AI_RESEARCH_BROWSER_E2E=1 \
python3 skills/software-development/oracle-ai-research-e2e/scripts/oracle_ai_research_e2e_check.py \
  --live \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --mode thinking \
  --cdp-port 9223 \
  --json
```

Use one flow first. Do not start a broad matrix until the single target has `status=verified` or an equally strong captured output plus screenshot evidence.

## Local Hermes Install

To install this skill into Hermes:

```bash
mkdir -p ~/.hermes/skills/software-development
cp -R skills/software-development/oracle-ai-research-e2e ~/.hermes/skills/software-development/
```

After install, restart or refresh the agent if the skill list is cached.

From a Hermes skill copy, pass the repo root when the current directory is not the public skills repo:

```bash
python3 ~/.hermes/skills/software-development/oracle-ai-research-e2e/scripts/oracle_ai_research_e2e_check.py \
  --repo-root /path/to/martins-awesome-skills \
  --quick \
  --json
```

## Common Mistakes

- Do not treat `oracle-plan` alone as a live E2E result. It proves command integration only.
- Do not run real E2E without `AI_RESEARCH_BROWSER_E2E=1`.
- Do not use Oracle runner when local guards are blocked; the CLI should mark `blocked-by-local-guards`.
- Do not use ChatGPT Pro/Extended Pro/GPT-5.5 Pro for routine tests.
- Do not commit real provider screenshots or full prompts unless they are explicitly sanitized.
