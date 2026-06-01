/**
 * Fetch the backend OpenAPI spec and generate TypeScript types.
 *
 * Usage: node scripts/codegen-api.mjs
 *
 * Reads BACKEND_URL from the environment (default http://localhost:8000).
 * Writes:
 *   lib/api/openapi.json  -- spec snapshot
 *   lib/api/types.ts      -- generated types (do not hand-edit)
 */

import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");

const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";
const specUrl = `${backendUrl}/openapi.json`;

console.log(`Fetching OpenAPI spec from ${specUrl} ...`);

const res = await fetch(specUrl);
if (!res.ok) {
  console.error(`Failed to fetch spec: HTTP ${res.status}`);
  process.exit(1);
}

const spec = await res.json();
const specPath = join(root, "lib", "api", "openapi.json");
writeFileSync(specPath, JSON.stringify(spec, null, 2) + "\n");
console.log(`Wrote spec snapshot -> lib/api/openapi.json`);

const typesPath = join(root, "lib", "api", "types.ts");
console.log(`Generating types -> lib/api/types.ts ...`);

execFileSync(
  "npx",
  ["openapi-typescript", "lib/api/openapi.json", "-o", "lib/api/types.ts"],
  { cwd: root, stdio: "inherit" },
);

console.log("Codegen complete.");
