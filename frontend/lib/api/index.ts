/**
 * Public surface of the API layer for the Presentation Context.
 *
 * Pages and components import ONLY from this file -- never from
 * lib/api/client.ts, lib/api/types.ts, or the concept modules
 * directly. This barrel re-exports only presentation-context types
 * and the two typed fetch helpers that return those types.
 *
 * Internal translate functions are not re-exported: pages and
 * components consume types + fetch helpers, not translators.
 *
 * Per architecture.md § Frontend: Smart-UI rejection.
 */

import "server-only";

export type { Citation } from "./citation";

export type {
  Jurisdiction,
  JurisdictionPage,
  MaterialSummary,
} from "./jurisdiction";
export { DENVER_SLUG, fetchJurisdictionPage } from "./jurisdiction";

export type { MaterialDetail, MaterialPage, Rule } from "./material";
export { fetchMaterialPage } from "./material";
