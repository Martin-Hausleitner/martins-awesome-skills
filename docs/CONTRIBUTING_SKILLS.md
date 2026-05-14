# Contributing Skills

Start from [`../templates/SKILL_TEMPLATE.md`](../templates/SKILL_TEMPLATE.md) when adding a new skill.

Good skills are small, specific, and easy for an agent to discover.

## A Good Skill Has

- `SKILL.md` with clear YAML frontmatter
- a trigger-focused `description`
- short procedural guidance
- scripts only when deterministic behavior matters
- tests for any script that talks to an API, parses files, or changes state

## Keep Out

- one-off project history
- private operational setup
- real credentials
- long tutorials that duplicate public docs
- generated logs and cache directories

## Suggested Structure

```text
my-skill/
  SKILL.md
  scripts/
  tests/
  references/
  templates/
```

Use only the folders you need.

## Public Review Checklist

- Does the skill work without private context?
- Are all examples placeholder-based?
- Are local machine paths removed?
- Can a stranger run the tests?
- Does the description say when to use the skill, not a full workflow summary?
