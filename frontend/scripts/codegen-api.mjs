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
import { readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import prettier from "prettier";

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

// openapi-typescript v7 emits unformatted output whose default indent
// has drifted across releases (2- vs 4-space). Normalize to the
// project's .prettierrc (2-space, no tabs) so a regen never churns
// indentation. The Prettier API ignores .prettierignore -- which lists
// this file to keep the pre-commit hook off it -- so the script stays
// the single formatter of its own output.
const generated = readFileSync(typesPath, "utf8");
const prettierConfig = await prettier.resolveConfig(typesPath);
const formatted = await prettier.format(generated, {
  ...prettierConfig,
  parser: "typescript",
});
writeFileSync(typesPath, formatted);
console.log(`Formatted -> lib/api/types.ts`);

console.log("Codegen complete.");
