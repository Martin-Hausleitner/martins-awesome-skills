---
name: comparison-deep-research
description: Use when the user asks to compare products, tools, GitHub repos, packages, frameworks, guides, platforms, plugins, or alternatives with Deep Research. Produces a strict research prompt and output format with at least 10 candidates, ideally 50, clickable GitHub and website links, five use-case-specific scoring categories, a 100-point total score, ranking, diagrams, and recommendation tables. Trigger on "vergleichen", "compare products", "best packages", "best tools", "GitHub links", "score 100", "rank platforms", "beste Programme", "Plugins vergleichen", or any broad comparison request that should become a reusable Deep Research scorecard.
version: 0.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [deep-research, comparison, scorecard, github, products, packages]
    related_skills: [ai-research-browser, ai-research-browser-cli, tool-comparison-heatmap, ai-research-output-publisher]
---

# Comparison Deep Research

Use this skill before starting Gemini/ChatGPT/Oracle Deep Research when the user wants products, repos, packages, tools, plugins, guides, platforms, or alternatives compared.

The skill's job is to convert a vague comparison request into a strict Deep Research prompt that always asks for:

- at least 10 candidates and ideally 50 when the domain is broad;
- verified GitHub repo links and official website/docs links;
- a comparison table where names are clickable and link columns are explicit;
- five major categories tailored to the use case;
- a 100-point weighted score for each candidate;
- category winners, overall winner, runner-ups, and "best for X" recommendations;
- at least one diagram or visual summary suitable for later rendering.

## Quick Use

Generate a prompt:

```bash
python3 skills/research/comparison-deep-research/scripts/comparison_deep_research_prompt.py \
  --topic "Discord voice agents and private assistants" \
  --use-case "private OpenClaw/Hermes-style Discord assistant that can speak live, run tasks, and post research results" \
  --candidate-count 50
```

Then pass the generated prompt into `ai-research-browser` or Oracle-assisted Deep Research.

## Required Deep Research Output

Tell the model to produce this structure:

1. **Executive Verdict**: winner, top 3, and when not to use the winner.
2. **Candidate Discovery**: explain search strategy and include excluded notable candidates.
3. **Scorecard Table**:
   - `Rank`
   - `Candidate` as a Markdown link to the official website/docs
   - `GitHub` as a Markdown link when available, or `N/A` with reason
   - `Type`
   - `License / Pricing`
   - `Last Activity`
   - five tailored category scores
   - `Total /100`
   - `Best For`
   - `Key Caveat`
4. **Five Category Definitions**: each category must have subcriteria and a fixed max score. The five categories must sum to 100.
5. **Mermaid Diagram**: quadrant, flow, or decision tree that helps choose between candidates.
6. **Detailed Notes Per Candidate**: concise evidence, links, and score rationale.
7. **Final Recommendation**: MVP choice, production choice, budget choice, self-hosted choice, safest choice.
8. **Next Steps**: concrete implementation or adoption plan.

## Scoring Rules

- Use exactly five top-level categories.
- Assign category weights that sum to 100.
- Score every candidate in every category.
- Total score must be the weighted sum, shown as `/100`.
- Do not invent links, stars, licenses, or dates. If a source cannot be verified, mark it `Unverified` and reduce confidence.
- For GitHub projects, verify repo URL, license, last meaningful activity, release/commit freshness, ecosystem activity, and maintenance signals.
- For non-GitHub products, verify official docs, pricing, security/compliance notes, and public roadmap or changelog.

## Integration Guidance

- Use `ai-research-browser` or `ai-research-browser-cli` for the browser run.
- Use `--allow-paid-quota-use` only when the user explicitly asked for Deep Research or a paid mode.
- Use `ai-research-output-publisher` after the report finishes to create a polished message, duration metrics, PSPin/deep-research links, and optional Notion payload.
- Use `tool-comparison-heatmap` after the research if the user wants an interactive visual matrix from the final data.

## Example Request Mapping

User: "Vergleiche die besten Obsidian AI Plugins."

Deep Research topic: "Best Obsidian AI plugins for rebuilding Notion-like team knowledge workflows."

Candidate count: `50` if available, minimum `10`.

Use-case categories might be:

- Notion-like knowledge management fit: 25
- AI/RAG capability: 20
- Team collaboration and sync: 20
- Data ownership and privacy: 20
- Maintenance, ecosystem, and ease of setup: 15
