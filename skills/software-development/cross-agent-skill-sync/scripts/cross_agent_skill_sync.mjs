#!/usr/bin/env node
import { createHash } from "node:crypto";
import {
  cpSync,
  existsSync,
  lstatSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  realpathSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { basename, dirname, join, relative, resolve } from "node:path";
import { homedir } from "node:os";

const repoRoot = resolve(process.cwd());
const args = parseArgs(process.argv.slice(2));
const warnings = [];
const defaultTargets = buildDefaultTargets();
const selectedTargets = resolveTargets(args.targets, args.targetRoots, defaultTargets);
const sourceRoots = args.sourceRoots.length ? args.sourceRoots : ["skills"];
const sources = discoverSources(sourceRoots, args.includeSkills);
const selectedSources = args.only.length
  ? sources.filter((source) => args.only.includes(source.name))
  : sources;
const sourceByName = new Map(sources.map((source) => [source.name, source]));

for (const required of args.requireSkills) {
  if (!sourceByName.has(required)) {
    warnings.push({
      code: "missing-required-skill",
      skill: required,
    });
  }
}

const actions = [];
for (const target of selectedTargets) {
  for (const source of selectedSources) {
    actions.push(planAction(source, target, args.strategy));
  }
}

if (args.execute) {
  for (const action of actions) {
    if (action.status === "install") {
      executeAction(action, args.strategy);
      action.status = "installed";
    }
  }
}

const report = {
  schema_version: 1,
  generated_by: "cross_agent_skill_sync.mjs",
  mode: args.execute ? "execute" : "plan",
  strategy: args.strategy,
  privacy: args.fullPaths ? "full-paths" : "home-redacted",
  targets: selectedTargets.map((target) => ({
    name: target.name,
    root: printablePath(target.root),
    layout: target.layout,
    enabled: target.enabled,
  })),
  sources: selectedSources.map((source) => ({
    name: source.name,
    path: printablePath(source.path),
    category_path: source.categoryPath,
    hash: source.hash,
  })),
  summary: summarize(actions, warnings),
  warnings,
  actions: actions.map((action) => printableAction(action)),
};

if (args.out) {
  writeFileSync(resolve(repoRoot, args.out), `${JSON.stringify(report, null, 2)}\n`);
}

if (args.json || args.out) {
  process.stdout.write(`${JSON.stringify(report.summary, null, 2)}\n`);
} else {
  printHuman(report);
}

if (args.failOnWarning && warnings.length) {
  process.exitCode = 1;
}

function parseArgs(rawArgs) {
  const parsed = {
    sourceRoots: [],
    includeSkills: [],
    targets: [],
    targetRoots: [],
    requireSkills: [],
    only: [],
    strategy: "symlink",
    execute: false,
    out: "",
    json: false,
    failOnWarning: false,
    fullPaths: false,
  };

  for (let index = 0; index < rawArgs.length; index += 1) {
    const arg = rawArgs[index];
    if (arg === "--source-root") {
      parsed.sourceRoots.push(rawArgs[++index]);
    } else if (arg === "--include-skill") {
      parsed.includeSkills.push(rawArgs[++index]);
    } else if (arg === "--target") {
      parsed.targets.push(rawArgs[++index]);
    } else if (arg === "--target-root") {
      parsed.targetRoots.push(rawArgs[++index]);
    } else if (arg === "--require-skill") {
      parsed.requireSkills.push(rawArgs[++index]);
    } else if (arg === "--only") {
      parsed.only.push(rawArgs[++index]);
    } else if (arg === "--strategy") {
      parsed.strategy = rawArgs[++index];
    } else if (arg === "--execute") {
      parsed.execute = true;
    } else if (arg === "--out") {
      parsed.out = rawArgs[++index];
    } else if (arg === "--json") {
      parsed.json = true;
    } else if (arg === "--fail-on-warning") {
      parsed.failOnWarning = true;
    } else if (arg === "--full-paths") {
      parsed.fullPaths = true;
    } else if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    } else {
      parsed.sourceRoots.push(arg);
    }
  }

  if (!["symlink", "copy"].includes(parsed.strategy)) {
    throw new Error(`Unsupported --strategy ${parsed.strategy}`);
  }

  return parsed;
}

function printHelp() {
  process.stdout.write(`Usage:
  node cross_agent_skill_sync.mjs [--target all] [--execute]

Options:
  --source-root <path>       Root containing SKILL.md folders. Defaults to ./skills.
  --include-skill <path>     Add one direct skill folder that contains SKILL.md.
  --target <name|all>        Target to project into. Repeatable.
  --target-root <spec>       Add a custom target as name=/path[:flat|preserve].
  --require-skill <name>     Warn when a required skill is missing. Repeatable.
  --only <name>              Project only this skill name. Repeatable.
  --strategy symlink|copy    Projection strategy. Defaults to symlink.
  --execute                  Apply install actions. Without this, only plans.
  --out <path>               Write full JSON report.
  --json                     Print summary JSON.
  --fail-on-warning          Exit non-zero if warnings exist.
  --full-paths               Do not redact the home directory in reports.
`);
}

function buildDefaultTargets() {
  const home = homedir();
  return [
    target("hermes", join(home, ".hermes", "skills"), "preserve"),
    target("codex", join(home, ".codex", "skills"), "flat"),
    target("agents", join(home, ".agents", "skills"), "flat"),
    target("openclaw", join(home, ".openclaw", "workspace", "skills"), "flat"),
    target("gemini", join(home, ".gemini", "skills"), "flat"),
    target("opencode", join(home, ".config", "opencode", "skills"), "flat"),
    target("claude", join(home, ".claude", "skills"), "flat"),
  ];
}

function target(name, root, layout) {
  return { name, root: resolvePath(root), layout, enabled: existsSync(resolvePath(root)) };
}

function resolveTargets(names, customSpecs, defaults) {
  const customTargets = customSpecs.map(parseTargetRoot);
  const byName = new Map([...defaults, ...customTargets].map((entry) => [entry.name, entry]));
  const requested = names.length ? names : ["all"];
  const result = [];

  for (const name of requested) {
    if (name === "all") {
      for (const entry of byName.values()) {
        if (entry.enabled) result.push(entry);
      }
      continue;
    }
    const entry = byName.get(name);
    if (!entry) {
      throw new Error(`Unknown target ${name}. Use --target-root ${name}=/path[:flat|preserve] for custom roots.`);
    }
    result.push(entry);
  }

  return uniqueTargets(result);
}

function parseTargetRoot(spec) {
  const match = spec.match(/^([^=]+)=(.+?)(?::(flat|preserve))?$/);
  if (!match) {
    throw new Error(`Invalid --target-root ${spec}; expected name=/path[:flat|preserve]`);
  }
  const root = resolvePath(match[2]);
  return {
    name: match[1],
    root,
    layout: match[3] || "flat",
    enabled: true,
  };
}

function uniqueTargets(targets) {
  const seen = new Set();
  return targets.filter((target) => {
    const key = `${target.name}:${target.root}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function discoverSources(roots, directSkills) {
  const discovered = [];
  for (const root of roots) {
    const absRoot = resolvePath(root);
    if (!existsSync(absRoot)) {
      warnings.push({ code: "missing-source-root", root: printablePath(absRoot) });
      continue;
    }
    if (existsSync(join(absRoot, "SKILL.md"))) {
      discovered.push(skillSource(absRoot, dirname(absRoot)));
    } else {
      scanForSkills(absRoot, absRoot, discovered);
    }
  }
  for (const direct of directSkills) {
    const absSkill = resolvePath(direct);
    if (!existsSync(join(absSkill, "SKILL.md"))) {
      warnings.push({ code: "missing-skill", path: printablePath(absSkill) });
      continue;
    }
    discovered.push(skillSource(absSkill, dirname(absSkill)));
  }

  return dedupeSources(discovered).sort((left, right) => left.name.localeCompare(right.name));
}

function scanForSkills(path, root, results) {
  const stat = lstatSync(path);
  if (!stat.isDirectory()) return;

  if (existsSync(join(path, "SKILL.md"))) {
    results.push(skillSource(path, root));
    return;
  }

  for (const entry of readdirSync(path)) {
    if (entry === ".git" || entry === "node_modules" || entry === "__pycache__" || entry === ".pytest_cache") {
      continue;
    }
    scanForSkills(join(path, entry), root, results);
  }
}

function skillSource(path, root) {
  const skillFile = join(path, "SKILL.md");
  const content = readFileSync(skillFile, "utf8");
  const frontmatter = parseFrontmatter(content);
  const name = frontmatter.name || basename(path);
  const rel = relative(root, path).split("\\").join("/");
  const categoryPath = rel === basename(path) ? "" : dirname(rel).replace(/^\.$/, "");
  return {
    name,
    path: resolve(path),
    categoryPath,
    hash: sha256(content),
  };
}

function dedupeSources(items) {
  const byName = new Map();
  for (const item of items) {
    if (!byName.has(item.name)) {
      byName.set(item.name, item);
      continue;
    }
    warnings.push({
      code: "duplicate-skill-name",
      skill: item.name,
      kept: printablePath(byName.get(item.name).path),
      skipped: printablePath(item.path),
    });
  }
  return [...byName.values()];
}

function planAction(source, target, strategy) {
  const destination = destinationFor(source, target);
  const action = {
    skill: source.name,
    target: target.name,
    strategy,
    source: source.path,
    destination,
    status: "install",
    reason: "destination-missing",
  };

  if (!existsSync(destination)) {
    return action;
  }

  const destStat = lstatSync(destination);
  if (destStat.isSymbolicLink()) {
    const real = realpathSync(destination);
    if (real === source.path) {
      return { ...action, status: "exists", reason: "already-linked" };
    }
    return { ...action, status: "conflict", reason: "symlink-points-elsewhere" };
  }

  if (destStat.isDirectory() && existsSync(join(destination, "SKILL.md"))) {
    const destHash = sha256(readFileSync(join(destination, "SKILL.md"), "utf8"));
    if (destHash === source.hash) {
      return { ...action, status: "exists", reason: "same-skill-hash" };
    }
    return { ...action, status: "exists", reason: "destination-exists-different-hash" };
  }

  return { ...action, status: "conflict", reason: "destination-not-skill-folder" };
}

function destinationFor(source, target) {
  if (target.layout === "preserve" && source.categoryPath) {
    return join(target.root, source.categoryPath, source.name);
  }
  return join(target.root, source.name);
}

function executeAction(action, strategy) {
  mkdirSync(dirname(action.destination), { recursive: true });
  if (strategy === "symlink") {
    symlinkSync(action.source, action.destination, "dir");
    return;
  }
  cpSync(action.source, action.destination, {
    recursive: true,
    filter: (path) => {
      const base = basename(path);
      return ![".git", "node_modules", "__pycache__", ".pytest_cache", ".DS_Store"].includes(base);
    },
  });
}

function parseFrontmatter(content) {
  if (!content.startsWith("---\n")) return {};
  const end = content.indexOf("\n---", 4);
  if (end === -1) return {};
  const parsed = {};
  for (const line of content.slice(4, end).split("\n")) {
    const match = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (match) parsed[match[1]] = match[2].replace(/^["']|["']$/g, "");
  }
  return parsed;
}

function summarize(actions, warningItems) {
  return {
    targets: new Set(actions.map((action) => action.target)).size,
    skills: new Set(actions.map((action) => action.skill)).size,
    actions: actions.length,
    by_status: countBy(actions, "status"),
    warnings: warningItems.length,
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

function printableAction(action) {
  return {
    skill: action.skill,
    target: action.target,
    strategy: action.strategy,
    source: printablePath(action.source),
    destination: printablePath(action.destination),
    status: action.status,
    reason: action.reason,
  };
}

function printablePath(path) {
  const resolved = resolvePath(path);
  if (args.fullPaths) return resolved;
  const home = homedir();
  if (resolved === home) return "~";
  if (resolved.startsWith(`${home}/`)) return `~/${relative(home, resolved).split("\\").join("/")}`;
  return resolved;
}

function resolvePath(path) {
  if (path === "~") return homedir();
  if (path.startsWith("~/")) return join(homedir(), path.slice(2));
  return resolve(repoRoot, path);
}

function printHuman(report) {
  process.stdout.write(`Cross-agent skill sync
mode: ${report.mode}
strategy: ${report.strategy}
targets: ${report.targets.map((target) => `${target.name}(${target.layout})`).join(", ") || "none"}
skills: ${report.summary.skills}
actions: ${report.summary.actions}
status: ${JSON.stringify(report.summary.by_status)}
warnings: ${report.summary.warnings}
`);
}

export {
  buildDefaultTargets,
  discoverSources,
  parseTargetRoot,
  planAction,
};
