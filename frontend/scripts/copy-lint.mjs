#!/usr/bin/env node
/**
 * Copy lint. Fails when a banned word appears in the UI sources: customers never see contest economics or
 * algorithm names. "Apex" is allowed only in the Launch page and below the marker in lib/copy.ts.
 *
 *   node scripts/copy-lint.mjs            # exits 1 with every hit listed
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const SCAN = ["app", "components", "lib"];
const SKIP = new Set(["lib/api-types.ts", "lib/technical.ts"]);
const BANNED = ["bounty", "bounties", "reward", "rewards", "tao", "subnet", "subnets", "miner", "miners", "emission", "emissions", "lightgbm", "xgboost", "logistic"];
const APEX_ALLOWED_FILES = new Set(["app/projects/[id]/launch/page.tsx"]);
const APEX_MARKER = "// --- apex allowed below ---";

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(tsx?|mjs|css)$/.test(name)) out.push(p);
  }
  return out;
}

const word = new RegExp(`\\b(${BANNED.join("|")})\\b`, "i");
const hits = [];
for (const dir of SCAN) {
  for (const file of walk(join(ROOT, dir))) {
    const rel = relative(ROOT, file);
    if (SKIP.has(rel)) continue;
    const text = readFileSync(file, "utf8");
    const marker = text.indexOf(APEX_MARKER);
    text.split("\n").forEach((line, i) => {
      const offset = text.split("\n").slice(0, i).join("\n").length;
      const m = line.match(word);
      if (m) hits.push(`${rel}:${i + 1}: banned word "${m[1]}": ${line.trim().slice(0, 100)}`);
      if (/\bApex\b/.test(line) && !APEX_ALLOWED_FILES.has(rel) && !(rel === "lib/copy.ts" && marker >= 0 && offset > marker)) {
        hits.push(`${rel}:${i + 1}: "Apex" outside the Launch screen: ${line.trim().slice(0, 100)}`);
      }
    });
  }
}
if (hits.length) {
  console.error(`copy lint: ${hits.length} problem${hits.length === 1 ? "" : "s"}`);
  for (const h of hits) console.error("  " + h);
  process.exit(1);
}
console.log("copy lint: clean");
