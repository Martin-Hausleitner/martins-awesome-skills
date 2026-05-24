import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { execFileSync } from "node:child_process";
import test from "node:test";
import assert from "node:assert/strict";

const repoRoot = resolve(import.meta.dirname, "..");
const doctor = join(repoRoot, "scripts", "skill-sync-doctor.mjs");

test("skill sync doctor emits manifest and adapter previews", () => {
  const fixture = mkdtempSync(join(tmpdir(), "skill-sync-doctor-"));
  const skillDir = join(fixture, "skills", "demo-skill");
  const docsDir = join(fixture, "docs");
  const outFile = join(fixture, "manifest.json");
  const emitDir = join(fixture, "generated");

  mkdirSync(skillDir, { recursive: true });
  mkdirSync(docsDir, { recursive: true });
  writeFileSync(
    join(skillDir, "SKILL.md"),
    `---
name: demo-skill
description: Demo skill for sync testing.
---

# Demo Skill

Use this for tests.
`,
  );
  writeFileSync(join(docsDir, "AGENTS.md"), "# Instructions\n");

  execFileSync(process.execPath, [
    doctor,
    "--root",
    join(fixture, "skills"),
    "--root",
    join(fixture, "docs"),
    "--out",
    outFile,
    "--emit",
    "codex",
    "--emit",
    "gemini",
    "--emit-dir",
    emitDir,
  ], { cwd: repoRoot, stdio: "pipe" });

  const manifest = JSON.parse(readFileSync(outFile, "utf8"));
  assert.equal(manifest.summary.total_assets, 2);
  assert.equal(manifest.summary.by_kind.skill, 1);
  assert.equal(manifest.summary.by_kind.workspace_instruction, 1);
  assert.equal(manifest.summary.by_policy.sync, 1);
  assert.equal(manifest.summary.by_policy.reference, 1);
  assert.deepEqual(manifest.warnings, []);

  const codex = JSON.parse(readFileSync(join(emitDir, "codex", "skills-index.json"), "utf8"));
  assert.equal(codex.target, "codex");
  assert.equal(codex.skills.length, 1);
  assert.equal(codex.skills[0].name, "demo-skill");

  const gemini = JSON.parse(readFileSync(join(emitDir, "gemini", "gemini-extension.preview.json"), "utf8"));
  assert.equal(gemini.name, "public-agent-skill-layer");
  assert.equal(gemini.skills.length, 1);
});

test("skill sync doctor marks credential-like paths for review", () => {
  const fixture = mkdtempSync(join(tmpdir(), "skill-sync-doctor-"));
  const skillDir = join(fixture, "skills", "github-auth");
  const outFile = join(fixture, "manifest.json");

  mkdirSync(skillDir, { recursive: true });
  writeFileSync(
    join(skillDir, "SKILL.md"),
    `---
name: github-auth
description: Configure GitHub auth safely.
---

# GitHub Auth
`,
  );

  execFileSync(process.execPath, [
    doctor,
    "--root",
    join(fixture, "skills"),
    "--out",
    outFile,
  ], { cwd: repoRoot, stdio: "pipe" });

  const manifest = JSON.parse(readFileSync(outFile, "utf8"));
  assert.equal(manifest.assets[0].sync_policy, "manual_review");
  assert.equal(manifest.assets[0].visibility, "review");
});

