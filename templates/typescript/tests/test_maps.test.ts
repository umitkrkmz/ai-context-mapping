/**
 * Self-guarding tests: the project map must describe every file and directory.
 *
 * Fails when a non-ignored path has no row in maps/project-map.md, when a row points at a path
 * that no longer exists, when rows are duplicated or malformed, when .agentignore hides the map,
 * or when CLAUDE.md drifts away from AGENTS.md.
 *
 * Runs unchanged under vitest. For Jest, delete the `vitest` import below (describe, it, and
 * expect are globals there), drop the message argument from each `expect(value, message)` call
 * (a vitest-only form), and run through ts-jest or Babel. Uses only Node built-ins.
 *
 * The project root is the current working directory; set PROJECT_ROOT to override it.
 */
import { describe, expect, it } from "vitest";
import { existsSync, lstatSync, readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";

const ROOT = resolve(process.env.PROJECT_ROOT ?? process.cwd());
const MAP_PATH = join(ROOT, "maps", "project-map.md");
const IGNORE_PATH = join(ROOT, ".agentignore");
const ALWAYS_IGNORED = [".git/", "node_modules/", "__pycache__/", ".pytest_cache/"];
const FILE_INDEX_TITLE = "file index";
const PLACEHOLDER = /\b(TODO|TBD|FIXME|XXX)\b|describe manually/i;
const CATEGORY_PATTERN = /^[a-z][a-z0-9-]*$/;

type Row = { path: string; category: string; purpose: string; invariants: string };
type IgnoreRule = { regex: RegExp; negate: boolean; dirOnly: boolean };

// ---------------------------------------------------------------------------------------------
// .agentignore handling (gitignore-style subset)
// ---------------------------------------------------------------------------------------------
function escapeRegex(char: string): string {
  return char.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");
}

function globToRegex(pattern: string): string {
  let out = "";
  let i = 0;
  while (i < pattern.length) {
    const char = pattern[i];
    if (char === "*") {
      if (pattern.slice(i, i + 2) === "**") {
        i += 2;
        if (pattern[i] === "/") {
          i += 1;
          out += "(?:.*/)?";
        } else {
          out += ".*";
        }
        continue;
      }
      out += "[^/]*";
    } else if (char === "?") {
      out += "[^/]";
    } else {
      out += escapeRegex(char);
    }
    i += 1;
  }
  return out;
}

function compileIgnoreRules(patterns: string[]): IgnoreRule[] {
  const rules: IgnoreRule[] = [];
  for (const raw of patterns) {
    let line = raw.trim();
    if (line === "" || line.startsWith("#")) continue;
    const negate = line.startsWith("!");
    if (negate) line = line.slice(1);
    const dirOnly = line.endsWith("/");
    line = line.replace(/\/+$/, "");
    if (line === "") continue;
    const anchored = line.startsWith("/") || line.includes("/");
    const body = globToRegex(line.replace(/^\/+/, ""));
    const regex = new RegExp(anchored ? `^${body}$` : `^(?:.*/)?${body}$`);
    rules.push({ regex, negate, dirOnly });
  }
  return rules;
}

function isIgnored(rules: IgnoreRule[], relPath: string, isDir: boolean): boolean {
  const parts = relPath.replace(/^\/+|\/+$/g, "").split("/");
  for (let depth = 1; depth <= parts.length; depth += 1) {
    const prefix = parts.slice(0, depth).join("/");
    const asDir = depth === parts.length ? isDir : true;
    let ignored = false;
    for (const rule of rules) {
      if (rule.dirOnly && !asDir) continue;
      if (rule.regex.test(prefix)) ignored = !rule.negate;
    }
    if (ignored) return true;
  }
  return false;
}

function loadRules(): IgnoreRule[] {
  const patterns = [...ALWAYS_IGNORED];
  if (existsSync(IGNORE_PATH)) {
    patterns.push(...readFileSync(IGNORE_PATH, "utf-8").split(/\r?\n/));
  }
  return compileIgnoreRules(patterns);
}

// ---------------------------------------------------------------------------------------------
// Repository and map readers
// ---------------------------------------------------------------------------------------------
function walkRepository(): string[] {
  const rules = loadRules();
  const found: string[] = [];
  const visit = (relDir: string): void => {
    const absolute = relDir === "" ? ROOT : join(ROOT, relDir);
    const names = readdirSync(absolute).sort();
    for (const name of names) {
      const rel = relDir === "" ? name : `${relDir}/${name}`;
      const stats = lstatSync(join(ROOT, rel));
      const isRealDir = stats.isDirectory();
      if (isIgnored(rules, rel, isRealDir)) continue;
      if (isRealDir) {
        found.push(`${rel}/`);
        visit(rel);
      } else {
        found.push(rel);
      }
    }
  };
  visit("");
  return found;
}

function splitRow(line: string): string[] {
  let text = line.trim();
  if (text.startsWith("|")) text = text.slice(1);
  if (text.endsWith("|") && !text.endsWith("\\|")) text = text.slice(0, -1);
  return text.split(/(?<!\\)\|/).map((cell) => cell.trim());
}

function readRows(): Row[] {
  const rows: Row[] = [];
  let inIndex = false;
  for (const line of readFileSync(MAP_PATH, "utf-8").split(/\r?\n/)) {
    const heading = /^##\s+(.+?)\s*$/.exec(line);
    if (heading) {
      inIndex = heading[1].toLowerCase().startsWith(FILE_INDEX_TITLE);
      continue;
    }
    if (!inIndex || !line.trimStart().startsWith("|")) continue;
    const cells = splitRow(line);
    if (cells.length < 4) continue;
    const match = /^`([^`]+)`$/.exec(cells[0]);
    if (match) {
      rows.push({ path: match[1], category: cells[1], purpose: cells[2], invariants: cells[3] });
    }
  }
  return rows;
}

function isDocumented(path: string, documented: Set<string>): boolean {
  if (documented.has(path)) return true;
  for (const entry of documented) {
    if (entry.endsWith("/**")) {
      const prefix = entry.slice(0, -2);
      if (path === prefix || path.startsWith(prefix)) return true;
    }
  }
  return false;
}

function normalized(path: string): string {
  return readFileSync(path, "utf-8").replace(/\r\n/g, "\n");
}

// ---------------------------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------------------------
describe("project map", () => {
  it("exists and has rows under '## File Index'", () => {
    expect(existsSync(MAP_PATH), "maps/project-map.md is missing").toBe(true);
    expect(readRows().length).toBeGreaterThan(0);
  });

  it("documents every non-ignored file and directory", () => {
    const documented = new Set(readRows().map((row) => row.path));
    const missing = walkRepository().filter((path) => !isDocumented(path, documented));
    expect(
      missing,
      `Paths missing from maps/project-map.md:\n  ${missing.join("\n  ")}\n` +
        "Add them with: python scripts/init_mapping.py --merge (then describe each new row).",
    ).toEqual([]);
  });

  it("has no stale entries", () => {
    const stale = readRows()
      .map((row) => row.path)
      .filter((path) => {
        const target = path.endsWith("/**") ? path.slice(0, -3) : path.replace(/\/+$/, "");
        return !existsSync(join(ROOT, target));
      });
    expect(stale, `Map entries whose paths no longer exist:\n  ${stale.join("\n  ")}`).toEqual([]);
  });

  it("has unique entries", () => {
    const seen = new Map<string, number>();
    for (const row of readRows()) seen.set(row.path, (seen.get(row.path) ?? 0) + 1);
    const duplicates = [...seen.entries()].filter(([, count]) => count > 1).map(([path]) => path);
    expect(duplicates).toEqual([]);
  });

  it("has well-formed rows without placeholders", () => {
    const problems: string[] = [];
    for (const { path, category, purpose, invariants } of readRows()) {
      if (path.includes("\\") || path.startsWith("./") || path.startsWith("/") || path.includes("//")) {
        problems.push(`${path}: use a repository-relative POSIX path`);
      }
      if (!CATEGORY_PATTERN.test(category)) problems.push(`${path}: invalid category '${category}'`);
      if (purpose.length < 8) problems.push(`${path}: purpose is too short to be useful`);
      if (PLACEHOLDER.test(purpose)) problems.push(`${path}: purpose still contains a placeholder`);
      if (invariants === "") problems.push(`${path}: write '-' in the invariants cell when none apply`);
    }
    expect(problems, problems.join("\n")).toEqual([]);
  });

  it("is not hidden by .agentignore", () => {
    const rules = loadRules();
    for (const path of ["maps/project-map.md", "AGENTS.md"]) {
      if (existsSync(join(ROOT, path))) {
        expect(isIgnored(rules, path, false), `.agentignore must not ignore ${path}`).toBe(false);
      }
    }
  });

  it("keeps CLAUDE.md identical to AGENTS.md", () => {
    const agents = join(ROOT, "AGENTS.md");
    const claude = join(ROOT, "CLAUDE.md");
    if (!existsSync(agents) || !existsSync(claude)) return;
    expect(normalized(claude)).toBe(normalized(agents));
  });
});
