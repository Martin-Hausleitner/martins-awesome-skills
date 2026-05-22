#!/usr/bin/env node
import { createHash } from "node:crypto";
import { existsSync, lstatSync, mkdirSync, readFileSync, readdirSync, realpathSync, writeFileSync } from "node:fs";
import { join, relative, resolve } from "node:path";

const PRIVATE_PATTERN = /\b(auth|cookie|credential|keychain|memory|oauth|password|private|secret|session|token)\b/i;
const SECRET_VALUE_PATTERN = /(api[_-]?key|bot[_-]?token|client[_-]?secret|password)\s*[:=]\s*(?!["']?<[^>]+>)(?!["']?\$\{)[A-Za-z0-9_./+=-]{12,}/i;
const MCP_CONFIG_PATTERN = /(^|[/\\])(\.mcp\.json|mcp\.json|mcp_settings\.json|settings\.json|opencode\.jsonc?|config\.toml)$/i;
const INSTRUCTION_PATTERN = /(^|[/\\])(AGENTS|CLAUDE|GEMINI)\.md$/i;

const args = parseArgs(process.argv.slice(2));
const roots = args.roots.length ? args.roots : ["skills"];
const repoRoot = process.cwd();

const assets = [];
const warnings = [];

for (const root of roots) {
  const absRoot = resolve(repoRoot, root);
  if (!existsSync(absRoot)) {
    warnings.push({ code: "missing-root", root });
    continue;
  }
  scan(absRoot, absRoot);
}

const manifest = {
  schema_version: 1,
  generated_by: "scripts/skill-sync-doctor.mjs",
  roots: roots.map((root) => relative(repoRoot, resolve(repoRoot, root)) || "."),
  summary: summarize(assets),
  warnings,
  assets,
};

if (args.out) {
  writeFileSync(resolve(repoRoot, args.out), `${JSON.stringify(manifest, null, 2)}\n`);
}

for (const target of args.emitTargets) {
  emitTarget(manifest, target);
}

if (args.json || args.out) {
  process.stdout.write(`${JSON.stringify(manifest.summary, null, 2)}\n`);
} else {
  printHuman(manifest);
}

if (args.failOnWarning && warnings.length) {
  process.exitCode = 1;
}

function parseArgs(rawArgs) {
  const parsed = {
    roots: [],
    out: "",
    json: false,
    failOnWarning: false,
    emitTargets: [],
    emitDir: ".skill-sync-generated",
  };

  for (let index = 0; index < rawArgs.length; index += 1) {
    const arg = rawArgs[index];
    if (arg === "--root") {
      parsed.roots.push(rawArgs[++index]);
    } else if (arg === "--out") {
      parsed.out = rawArgs[++index];
    } else if (arg === "--json") {
      parsed.json = true;
    } else if (arg === "--emit") {
      parsed.emitTargets.push(rawArgs[++index]);
    } else if (arg === "--emit-dir") {
      parsed.emitDir = rawArgs[++index];
    } else if (arg === "--fail-on-warning") {
      parsed.failOnWarning = true;
    } else if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    } else {
      parsed.roots.push(arg);
    }
  }

  return parsed;
}

function printHelp() {
  process.stdout.write(`Usage:
  node scripts/skill-sync-doctor.mjs [--root skills] [--root docs] [--out manifest.json]

Options:
  --root <path>       Scan an additional root. Defaults to ./skills.
  --out <path>        Write full manifest JSON to this path.
  --emit <target>     Emit adapter preview for codex or gemini. Repeatable.
  --emit-dir <path>   Directory for emitted adapter previews.
  --json              Print summary JSON instead of human text.
  --fail-on-warning   Exit non-zero when warnings are found.
`);
}

function scan(path, root) {
  const stat = lstatSync(path);
  if (stat.isSymbolicLink()) {
    const real = realpathSync(path);
    warnings.push({
      code: "symlink",
      path: toRepoPath(path),
      target: toRepoPath(real),
    });
  }

  if (stat.isDirectory()) {
    for (const entry of readdirSync(path)) {
      if (entry === ".git" || entry === "node_modules" || entry === ".pytest_cache") {
        continue;
      }
      scan(join(path, entry), root);
    }
    return;
  }

  if (!stat.isFile()) {
    return;
  }

  const repoPath = toRepoPath(path);
  const relToRoot = relative(root, path);

  if (relToRoot === "SKILL.md" || repoPath.endsWith("/SKILL.md")) {
    assets.push(skillAsset(path, repoPath));
    return;
  }

  if (MCP_CONFIG_PATTERN.test(repoPath)) {
    assets.push(genericAsset(path, repoPath, "mcp_config"));
    return;
  }

  if (INSTRUCTION_PATTERN.test(repoPath)) {
    assets.push(genericAsset(path, repoPath, "workspace_instruction"));
  }
}

function skillAsset(path, repoPath) {
  const content = readFileSync(path, "utf8");
  const frontmatter = parseFrontmatter(content);
  const id = repoPath.split("/").slice(0, -1).join("/") || repoPath;
  const missing = [];

  if (!frontmatter.name) missing.push("name");
  if (!frontmatter.description) missing.push("description");

  for (const field of missing) {
    warnings.push({
      code: "missing-skill-frontmatter",
      field,
      path: repoPath,
    });
  }

  return {
    id,
    kind: "skill",
    path: repoPath,
    name: frontmatter.name || id.split("/").pop(),
    description: frontmatter.description || "",
    hash: sha256(content),
    visibility: visibilityFor(repoPath, content),
    sync_policy: syncPolicyFor(repoPath, content),
    frontmatter,
  };
}

function genericAsset(path, repoPath, kind) {
  const content = readFileSync(path, "utf8");
  return {
    id: repoPath,
    kind,
    path: repoPath,
    hash: sha256(content),
    visibility: visibilityFor(repoPath, content),
    sync_policy: syncPolicyFor(repoPath, content),
  };
}

function parseFrontmatter(content) {
  if (!content.startsWith("---\n")) {
    return {};
  }

  const end = content.indexOf("\n---", 4);
  if (end === -1) {
    return {};
  }

  const frontmatter = {};
  const block = content.slice(4, end).split("\n");
  for (const line of block) {
    const match = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (!match) {
      continue;
    }
    frontmatter[match[1]] = match[2].replace(/^["']|["']$/g, "");
  }
  return frontmatter;
}

function visibilityFor(repoPath, content) {
  if (PRIVATE_PATTERN.test(repoPath) || SECRET_VALUE_PATTERN.test(content)) {
    return "review";
  }
  return "public";
}

function syncPolicyFor(repoPath, content) {
  if (PRIVATE_PATTERN.test(repoPath) || SECRET_VALUE_PATTERN.test(content)) {
    return "manual_review";
  }
  if (MCP_CONFIG_PATTERN.test(repoPath)) {
    return "redact";
  }
  if (INSTRUCTION_PATTERN.test(repoPath)) {
    return "reference";
  }
  return "sync";
}

function summarize(items) {
  return {
    total_assets: items.length,
    by_kind: countBy(items, "kind"),
    by_policy: countBy(items, "sync_policy"),
    by_visibility: countBy(items, "visibility"),
  };
}

function countBy(items, key) {
  return items.reduce((acc, item) => {
    acc[item[key]] = (acc[item[key]] || 0) + 1;
    return acc;
  }, {});
}

function sha256(content) {
  return createHash("sha256").update(content).digest("hex");
}

function toRepoPath(path) {
  return relative(repoRoot, path).split("\\").join("/");
}

function printHuman(manifest) {
  process.stdout.write(`Skill sync doctor
roots: ${manifest.roots.join(", ")}
assets: ${manifest.summary.total_assets}
kinds: ${JSON.stringify(manifest.summary.by_kind)}
policies: ${JSON.stringify(manifest.summary.by_policy)}
visibility: ${JSON.stringify(manifest.summary.by_visibility)}
warnings: ${manifest.warnings.length}
`);
}

function emitTarget(manifest, target) {
  const normalizedTarget = target.toLowerCase();
  const emitters = {
    codex: emitCodexPreview,
    gemini: emitGeminiPreview,
  };

  const emitter = emitters[normalizedTarget];
  if (!emitter) {
    warnings.push({
      code: "unknown-emit-target",
      target,
      supported: Object.keys(emitters),
    });
    return;
  }

  const outputDir = resolve(repoRoot, args.emitDir, normalizedTarget);
  mkdirSync(outputDir, { recursive: true });
  emitter(manifest, outputDir);
}

function emitCodexPreview(manifest, outputDir) {
  const skills = syncableSkills(manifest);
  const payload = {
    schema_version: 1,
    target: "codex",
    generated_by: manifest.generated_by,
    note: "Adapter preview only. Review before projecting into Codex config or skill roots.",
    skills,
  };
  writeFileSync(join(outputDir, "skills-index.json"), `${JSON.stringify(payload, null, 2)}\n`);
}

function emitGeminiPreview(manifest, outputDir) {
  const skills = syncableSkills(manifest);
  const payload = {
    name: "public-agent-skill-layer",
    version: "0.0.0",
    description: "Adapter preview generated from public SKILL.md inventory.",
    generated_by: manifest.generated_by,
    note: "Adapter preview only. Review before turning this into a Gemini extension.",
    skills,
    mcpServers: {},
  };
  writeFileSync(join(outputDir, "gemini-extension.preview.json"), `${JSON.stringify(payload, null, 2)}\n`);
}

function syncableSkills(manifest) {
  return manifest.assets
    .filter((asset) => asset.kind === "skill" && asset.sync_policy === "sync")
    .map((asset) => ({
      name: asset.name,
      path: asset.path,
      description: asset.description,
      hash: asset.hash,
    }))
    .sort((left, right) => left.name.localeCompare(right.name));
}
