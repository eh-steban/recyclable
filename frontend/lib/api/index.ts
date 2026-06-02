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

export type {
  Answer,
  AskInput,
  AskResult,
  Facility,
  JurisdictionRef,
  UnresolvedJurisdiction,
} from "./ask";
export { fetchAsk } from "./ask";
