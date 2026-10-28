#!/usr/bin/env node
/**
 * Copy lint. Fails when a banned word appears in the UI sources: customers never see contest economics or
 * algorithm names. "Apex" is allowed only in the Launch page and below the marker in lib/copy.ts.
 *
 * Decision words (reject, deny, approve, terminate, ...) are banned too: lists about people offer support ("reach
 * out", "follow up", "check in"), they never decide about anyone. The people templates' own text in
 * data/templates/<id>/defaults.json ("people": true) and their saved intake replies (intake_cache.json) are
 * checked for the same words, plus "flag".
 *
 *   node scripts/copy-lint.mjs            # exits 1 with every hit listed
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const SCAN = ["app", "components", "lib"];
const SKIP = new Set(["lib/api-types.ts", "lib/technical.ts"]);
const BANNED = ["bounty", "bounties", "reward", "rewards", "tao", "subnet", "subnets", "miner", "miners", "emission", "emissions", "lightgbm", "xgboost", "logistic"];
const DECISION = [
  "reject", "rejects", "rejected", "rejecting", "rejection",
  "deny", "denies", "denied", "denying", "denial",
  "decline", "declines", "declined", "declining",
  "approve", "approves", "approved", "approving", "approval",
  "terminate", "terminated", "terminating", "termination",
  "fire", "fired", "firing",
  "disqualify", "disqualified", "blacklist", "blacklisted",
];
const PEOPLE_EXTRA = ["flag", "flags", "flagged", "flagging"];
const TEMPLATES = join(ROOT, "..", "data", "templates");
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
const decision = new RegExp(`\\b(${DECISION.join("|")})\\b`, "i");
const peopleWord = new RegExp(`\\b(${[...DECISION, ...PEOPLE_EXTRA].join("|")})\\b`, "i");
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
      const d = line.match(decision);
      if (d) hits.push(`${rel}:${i + 1}: decision word "${d[1]}" (use support language): ${line.trim().slice(0, 100)}`);
      if (/\bApex\b/.test(line) && !APEX_ALLOWED_FILES.has(rel) && !(rel === "lib/copy.ts" && marker >= 0 && offset > marker)) {
        hits.push(`${rel}:${i + 1}: "Apex" outside the Launch screen: ${line.trim().slice(0, 100)}`);
      }
    });
  }
}
// People templates: every string in defaults.json (card, words, intake replies, list framing).
function strings(v, path, out) {
  if (typeof v === "string") out.push([path, v]);
  else if (Array.isArray(v)) v.forEach((x, i) => strings(x, `${path}[${i}]`, out));
  else if (v && typeof v === "object") for (const [k, x] of Object.entries(v)) strings(x, path ? `${path}.${k}` : k, out);
  return out;
}
for (const id of readdirSync(TEMPLATES)) {
  const p = join(TEMPLATES, id, "defaults.json");
  let cfg;
  try {
    cfg = JSON.parse(readFileSync(p, "utf8"));
  } catch {
    continue;
  }
  if (!cfg.people) continue;
  for (const [path, s] of strings(cfg, "", [])) {
    const m = s.match(peopleWord);
    if (m) hits.push(`data/templates/${id}/defaults.json ${path}: decision word "${m[1]}" in a people template: ${s.slice(0, 100)}`);
  }
  // the saved intake replies are replayed to users word for word
  let cache = {};
  try {
    cache = JSON.parse(readFileSync(join(TEMPLATES, id, "intake_cache.json"), "utf8"));
  } catch {}
  for (const [key, entry] of Object.entries(cache)) {
    const m = String(entry?.message ?? "").match(peopleWord);
    if (m) hits.push(`data/templates/${id}/intake_cache.json ${key.slice(0, 12)}: decision word "${m[1]}" in a saved reply: ${String(entry.message).slice(0, 100)}`);
  }
}

if (hits.length) {
  console.error(`copy lint: ${hits.length} problem${hits.length === 1 ? "" : "s"}`);
  for (const h of hits) console.error("  " + h);
  process.exit(1);
}
console.log("copy lint: clean");
