import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";
import assert from "node:assert/strict";

const repoRoot = resolve(import.meta.dirname, "..");

function read(path) {
  return readFileSync(resolve(repoRoot, path), "utf8");
}

test("ambiguous Deep Research intent routes to Comet Gemini preflight first", () => {
  const browserSkill = read("skills/software-development/ai-research-browser/SKILL.md");
  const cliSkill = read("skills/software-development/ai-research-browser-cli/SKILL.md");
  const installProof = read("docs/CROSS_AGENT_INSTALL_PROOF.md");

  for (const text of [browserSkill, cliSkill, installProof]) {
    assert.match(text, /Starte Deep Research/);
    assert.match(text, /Comet \+ Gemini|Comet\/Gemini|comet[\s\S]*provider: `google`/i);
  }

  assert.match(browserSkill, /--browser comet[\s\S]*--provider google[\s\S]*--port 9333/);
  assert.match(cliSkill, /--browser comet --profile work --provider google --mode deep-research --cdp-port 9333/);
  assert.match(cliSkill, /do not route to a\s+Brave-first fallback/i);
});

test("Deep Research prompt budget is documented for agents", () => {
  const budgets = read("docs/DEEP_RESEARCH_PROMPT_BUDGETS.md");
  const cliSkill = read("skills/software-development/ai-research-browser-cli/SKILL.md");
  const comparisonSkill = read("skills/research/comparison-deep-research/SKILL.md");

  for (const text of [budgets, cliSkill, comparisonSkill]) {
    assert.match(text, /6,000/);
    assert.match(text, /12,000/);
    assert.match(text, /24,000/);
  }

  assert.match(budgets, /do not paste into provider UI/i);
  assert.match(cliSkill, /deep_research_prompt_budget\.py/);
});
