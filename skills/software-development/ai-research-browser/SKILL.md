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

- Discovers installed Chromium-family browsers: Brave, Comet/Komet, Google Chrome, and Microsoft Edge.
- Reads Chromium profile metadata from `Local State` and `Preferences`, including profile directory, display name, and visible account email when available.
- Resolves profile aliases such as `work` by exact profile/account match first, then by a Work/Arbeit name match.
- Produces launch arguments for headless or background runs with `--remote-debugging-port`, `--user-data-dir`, and `--profile-directory`.
- Supports provider modes for ChatGPT chat, ChatGPT Deep Research, ChatGPT Agent, Gemini chat, Gemini Deep Research, Gemini Agent, Claude chat/research/artifacts, Perplexity research, and Grok/Grog research.
- Builds a full browser x profile x provider x feature test matrix for systematic E2E runs.
- Provides an interactive wizard that lets a human choose the installed browser, profile, provider, and feature before launching or testing.
- Archives existing provider chats into a local cache so later runs can continue from cached transcripts or intentionally refresh by scraping again.
- Records E2E evidence as a `status.json` plus screenshot path, so a human can verify whether the provider UI actually entered the requested mode.

## Safety Rule

Do not quit or relaunch the user's already-open browser without explicit permission. If a browser is already running without `--remote-debugging-port`, run preflight and report the blocker. For live UI checks, use Computer Use against the existing window and record screenshots locally.

Do not commit private screenshots that contain account names, chat history, or private prompts to a public repository. Keep them as local artifacts unless the user explicitly asks for a sanitized export.

## Commands

Discover browsers, profiles, providers, modes, and known model labels:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py discover
```

Build the full test matrix:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py matrix --json
```

Save the matrix for a later E2E run:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py matrix \
  --json \
  --output /tmp/ai-research-browser-matrix.json
```

Use the interactive picker:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py wizard --headful
```

Capture account/login/quota status from visible provider UI text:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py accounts \
  --browser brave \
  --profile work \
  --provider chatgpt \
  --text-file /tmp/chatgpt-visible-text.txt
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
  --mode deep-research
```

Use `--headful` when you need to see the browser or when a provider blocks headless mode.

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

This follows the same shape that makes Peter Steinberger's Peekaboo useful for agents: separate discovery/snapshot JSON from actions. The `matrix` command is the snapshot, while `wizard`, `launch-args`, `verify-text`, and `record-e2e` are the action/evidence layer.

## Testing

Run unit tests from the repository root:

```bash
python3 -m unittest discover -s skills/software-development/ai-research-browser/tests -p 'test_*.py'
```
