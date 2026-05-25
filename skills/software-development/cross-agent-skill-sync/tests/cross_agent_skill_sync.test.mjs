import { execFileSync } from "node:child_process";
import { existsSync, lstatSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { mkdtempSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";

const repoRoot = resolve(import.meta.dirname, "../../../..");
const script = join(repoRoot, "skills", "software-development", "cross-agent-skill-sync", "scripts", "cross_agent_skill_sync.mjs");

test("plans and executes additive copy projection without overwriting existing skills", () => {
  const fixture = mkdtempSync(join(tmpdir(), "cross-agent-skill-sync-"));
  const sourceRoot = join(fixture, "repo", "skills");
  const skillDir = join(sourceRoot, "software-development", "demo-skill");
  const targetRoot = join(fixture, "target-skills");
  const outFile = join(fixture, "report.json");

  mkdirSync(skillDir, { recursive: true });
  mkdirSync(targetRoot, { recursive: true });
  writeSkill(skillDir, "demo-skill");

  execFileSync(process.execPath, [
    script,
    "--source-root",
    sourceRoot,
    "--target-root",
    `test=${targetRoot}:preserve`,
    "--target",
    "test",
    "--strategy",
    "copy",
    "--execute",
    "--out",
    outFile,
  ], { cwd: repoRoot, stdio: "pipe", env: { ...process.env, HOME: fixture } });

  const report = JSON.parse(readFileSync(outFile, "utf8"));
  assert.equal(report.summary.by_status.installed, 1);
  assert.ok(existsSync(join(targetRoot, "software-development", "demo-skill", "SKILL.md")));

  const secondOut = join(fixture, "second-report.json");
  execFileSync(process.execPath, [
    script,
    "--source-root",
    sourceRoot,
    "--target-root",
    `test=${targetRoot}:preserve`,
    "--target",
    "test",
    "--strategy",
    "copy",
    "--out",
    secondOut,
  ], { cwd: repoRoot, stdio: "pipe", env: { ...process.env, HOME: fixture } });

  const secondReport = JSON.parse(readFileSync(secondOut, "utf8"));
  assert.equal(secondReport.summary.by_status.exists, 1);
});

test("symlink strategy creates links and redacts home paths by default", () => {
  const fixture = mkdtempSync(join(tmpdir(), "cross-agent-skill-sync-"));
  const sourceRoot = join(fixture, "repo", "skills");
  const skillDir = join(sourceRoot, "demo-skill");
  const targetRoot = join(fixture, ".codex", "skills");
  const outFile = join(fixture, "report.json");

  mkdirSync(skillDir, { recursive: true });
  mkdirSync(targetRoot, { recursive: true });
  writeSkill(skillDir, "demo-skill");

  execFileSync(process.execPath, [
    script,
    "--source-root",
    sourceRoot,
    "--target-root",
    `codex=${targetRoot}:flat`,
    "--target",
    "codex",
    "--execute",
    "--out",
    outFile,
  ], { cwd: repoRoot, stdio: "pipe", env: { ...process.env, HOME: fixture } });

  const destination = join(targetRoot, "demo-skill");
  assert.ok(lstatSync(destination).isSymbolicLink());

  const reportText = readFileSync(outFile, "utf8");
  assert.ok(reportText.includes("~/"));
  assert.ok(!reportText.includes(fixture));
});

test("hermes target uses copy projection even when symlink strategy is requested", () => {
  const fixture = mkdtempSync(join(tmpdir(), "cross-agent-skill-sync-"));
  const sourceRoot = join(fixture, "repo", "skills");
  const skillDir = join(sourceRoot, "software-development", "demo-skill");
  const targetRoot = join(fixture, ".hermes", "skills");
  const outFile = join(fixture, "report.json");

  mkdirSync(skillDir, { recursive: true });
  mkdirSync(targetRoot, { recursive: true });
  writeSkill(skillDir, "demo-skill");

  execFileSync(process.execPath, [
    script,
    "--source-root",
    sourceRoot,
    "--target-root",
    `hermes=${targetRoot}:preserve`,
    "--target",
    "hermes",
    "--strategy",
    "symlink",
    "--execute",
    "--out",
    outFile,
  ], { cwd: repoRoot, stdio: "pipe", env: { ...process.env, HOME: fixture } });

  const destination = join(targetRoot, "software-development", "demo-skill");
  assert.equal(lstatSync(destination).isSymbolicLink(), false);
  assert.ok(existsSync(join(destination, "SKILL.md")));

  const report = JSON.parse(readFileSync(outFile, "utf8"));
  assert.equal(report.actions[0].strategy, "copy");
});

test("required missing skill is reported and can fail the run", () => {
  const fixture = mkdtempSync(join(tmpdir(), "cross-agent-skill-sync-"));
  const sourceRoot = join(fixture, "skills");
  const targetRoot = join(fixture, "target");
  mkdirSync(sourceRoot, { recursive: true });
  mkdirSync(targetRoot, { recursive: true });

  let failed = false;
  try {
    execFileSync(process.execPath, [
      script,
      "--source-root",
      sourceRoot,
      "--target-root",
      `test=${targetRoot}:flat`,
      "--target",
      "test",
      "--require-skill",
      "codex-computer-use-eu-activate",
      "--fail-on-warning",
    ], { cwd: repoRoot, stdio: "pipe", env: { ...process.env, HOME: fixture } });
  } catch (error) {
    failed = true;
    assert.equal(error.status, 1);
  }
  assert.equal(failed, true);
});

function writeSkill(directory, name) {
  writeFileSync(
    join(directory, "SKILL.md"),
    `---
name: ${name}
description: Demo skill for cross-agent sync testing.
---

# ${name}

Use this in tests.
`,
  );
}
