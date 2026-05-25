# Deep Research Prompt Budgets

This document gives agents conservative text budgets for browser-based Deep
Research prompts. These are not provider hard limits. They are operational
guardrails to avoid huge pasted prompts, over-broad research plans, missed
details, rate-limit pressure, and oversized final reports.

## Why This Exists

Deep Research tends to expand a short request into a plan, searches, source
reading, synthesis, and a long final report. Very large initial prompts make the
run slower, less stable, and harder to verify. Agents should pass a compact
research brief and attach/source larger context separately.

## Agent-Safe Text Budgets

| Level | Characters | Approx. Tokens | Action |
|---|---:|---:|---|
| `ideal` | `<= 6,000` | `<= 1,500` | Safe for normal Deep Research prompts |
| `standard_max` | `<= 12,000` | `<= 3,000` | Default maximum for automated UI submits |
| `review` | `12,001-24,000` | `3,001-6,000` | Ask for confirmation or compress first |
| `block` | `> 24,000` | `> 6,000` | Do not paste into provider UI; summarize or attach files |

Use the same budget for ChatGPT, Gemini, Perplexity, Grok, and Claude UI-based
Deep Research/Agent flows unless a provider-specific guard is stricter.

## Prompt Shape

Keep the initial prompt to this structure:

1. Goal: one sentence.
2. Scope: what to include and exclude.
3. Decision criteria: 3-7 bullets.
4. Output format: table/report/scorecard requirements.
5. Constraints: date freshness, geography, budget, privacy, integrations.
6. Known candidates/sources: names and links only, no long pasted pages.

For comparison research, request discovery of `10-50` candidates, but do not
paste long descriptions for all candidates. If you already have many sources,
attach a file or provide a concise link list.

## Market Exhaustive Research

When the user wants the market fully explored, use an exhaustive brief instead
of a huge prompt:

- Ask for as many verifiable candidates as reasonable.
- Require a longlist, then a scored shortlist.
- Include adjacent categories and long-tail tools.
- Ask the model to report search queries, source types, excluded candidates, and
  market gaps.
- Put large user context in attached files: known candidates, prior notes,
  constraints, CSV exports, screenshots, PDFs, or link lists.

Even in exhaustive mode, keep the prompt body within the `standard_max` budget
when possible. The extra breadth should come from Deep Research discovery and
attached context files, not from pasting a massive prebuilt market dump.

## Provider Notes From Current Public Docs

- OpenAI documents file-upload limits for ChatGPT: `512 MB` per file, `2M`
  tokens for text/document files, `20 MB` per image, and upload-rate/storage
  caps. Use files for large context instead of pasting huge prompt text.
- OpenAI's Deep Research API docs describe prompt clarification/rewriting and
  note that directly placing large private data in prompt text is the simplest
  but not the most scalable approach; file search, connectors, or MCP are better
  for large/private corpora.
- Google documents Gemini file-upload limits: up to `10` files per prompt,
  `100 MB` for most non-video files, `2 GB` per video, audio/video duration
  limits, and larger context windows on paid plans. Google also warns that very
  large uploads can lead to missed connections or details.
- Gemini Deep Research starts by turning the prompt into a research plan. That
  plan step is the right place to keep the brief compact and focused.

Sources:

- OpenAI File Uploads FAQ: https://help.openai.com/en/articles/8555545-uploading-files-in-chatgpt
- OpenAI Deep Research API guide: https://developers.openai.com/api/docs/guides/deep-research
- Gemini file upload help: https://support.google.com/gemini/answer/14903178
- Gemini Deep Research overview: https://gemini.google/overview/deep-research/

## Required Agent Behavior

- Before any paid Deep Research submit, measure the prompt.
- If `review`, compress the prompt or ask the user whether to proceed.
- If `block`, do not submit. Convert large context into files, a link list, or a
  staged plan.
- Never use live provider testing to probe maximum limits by spamming long
  prompts. Use official docs, local prompt measurement, and conservative
  budgets.
- Record the prompt-budget status in the run artifact/status when possible.
