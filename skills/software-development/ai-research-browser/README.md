# AI Research Browser

Inventory and test AI providers across your installed browser profiles.

This skill gives Hermes a local CLI for discovering installed Chromium-family browsers, finding their profiles, selecting a provider such as ChatGPT, Gemini, Claude, Perplexity, or Grok, and recording evidence for each tested AI feature.

It is designed for the real-world macOS setup where Brave, Comet/Komet, Chrome, and Edge may already be open with different accounts. The CLI does not blindly quit or relaunch those browsers; it reports blockers and lets you choose whether to run headful, headless, or via Computer Use.

## Quick Start

From the repository root:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py discover
```

Build the full browser x profile x provider x feature matrix:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py matrix --json \
  --output /tmp/ai-research-browser-matrix.json
```

Use the interactive picker:

```bash
python3 skills/software-development/ai-research-browser/scripts/ai_research_browser.py wizard --headful
```

The wizard prints pure JSON to stdout, so it can be piped into other scripts.

## Providers

Current provider registry:

- ChatGPT: `chat`, `deep-research`, `agent`
- Gemini: `chat`, `deep-research`, `agent`
- Claude: `chat`, `research`, `artifacts`
- Perplexity: `chat`, `research`
- Grok: `chat`, `research`

`grog` and `xai` are accepted aliases for `grok`.

## Browser Support

The CLI currently discovers:

- Brave Browser
- Comet/Komet
- Google Chrome
- Microsoft Edge

Profiles are read from Chromium `Local State` and `Preferences`, including display name and account email when Chromium exposes it.

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
- Deep Research remaining count, when visible
- Agent task remaining count, when visible

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
  --mode research \
  --headful
```

Without `--headful`, the generated command includes `--headless=new`.

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

This follows the pattern that makes Peter Steinberger's Peekaboo useful for agents: keep discovery/snapshot data as structured JSON, then run actions and verification against that state. The CLI therefore separates:

- `discover` and `matrix`: inventory/snapshot
- `preflight`: blocker detection
- `wizard` and `launch-args`: selected action plan
- `verify-text` and `record-e2e`: evidence capture

## Tests

```bash
python3 -m unittest discover -s skills/software-development/ai-research-browser/tests -p 'test_*.py'
```
