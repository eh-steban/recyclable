/**
 * Public surface of the API layer for the Presentation Context.
 * Pages and components import ONLY from this file (the ACL barrel).
 *
 * Per architecture.md § Frontend: Smart-UI rejection. The full rule --
 * the import-only-from-here discipline and why translators are not
 * re-exported -- lives in frontend-mental-model.md § Architectural
 * commitments.
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
