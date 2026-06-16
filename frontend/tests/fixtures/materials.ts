import type { MaterialSummary } from "@/lib/api/jurisdiction";
import type { MaterialDetail, MaterialPage, Rule } from "@/lib/api/material";
import type { components } from "@/lib/api/types";
import { makeCitation, makeWireCitation } from "./citations";
import { makeJurisdiction } from "./jurisdictions";

type WireMaterialSummary = components["schemas"]["MaterialSummaryWire"];
type WireMaterialDetail = components["schemas"]["MaterialDetailWire"];
type WireRule = components["schemas"]["RuleWire"];

export const ALUMINUM_MATERIAL_ID = "00000000-0000-0000-0000-000000000002";

export function makeMaterialSummary(
  overrides: Partial<MaterialSummary> = {},
): MaterialSummary {
  return {
    id: ALUMINUM_MATERIAL_ID,
    slug: "aluminum-cans",
    canonicalName: "Aluminum Cans",
    acceptedStatus: "accepted",
    needsPreparation: false,
    citation: makeCitation({ quote: null }),
    ...overrides,
  };
}

export function makeMaterialDetail(
  overrides: Partial<MaterialDetail> = {},
): MaterialDetail {
  return {
    id: ALUMINUM_MATERIAL_ID,
    slug: "aluminum-cans",
    canonicalName: "Aluminum Cans",
    ...overrides,
  };
}

export function makeRule(overrides: Partial<Rule> = {}): Rule {
  return {
    disposition: "curbside_recycle",
    acceptedStatus: "accepted",
    preparationSteps: [],
    exceptions: [],
    warnings: [],
    ...overrides,
  };
}

export function makePage(overrides: Partial<MaterialPage> = {}): MaterialPage {
  return {
    jurisdiction: makeJurisdiction(),
    material: makeMaterialDetail(),
    rule: makeRule(),
    citations: [makeCitation()],
    ...overrides,
  };
}

/** Wire-shape material summary fed to the translateJurisdictionPage boundary. */
export function makeWireMaterialSummary(
  overrides: Partial<WireMaterialSummary> = {},
): WireMaterialSummary {
  return {
    id: ALUMINUM_MATERIAL_ID,
    slug: "aluminum-cans",
    canonical_name: "Aluminum Cans",
    accepted_status: "accepted",
    needs_preparation: false,
    citation: makeWireCitation(),
    ...overrides,
  };
}

/** Wire-shape material detail fed to the translateMaterialPage boundary. */
export function makeWireMaterialDetail(
  overrides: Partial<WireMaterialDetail> = {},
): WireMaterialDetail {
  return {
    id: ALUMINUM_MATERIAL_ID,
    slug: "aluminum-cans",
    canonical_name: "Aluminum Cans",
    ...overrides,
  };
}

/** Wire-shape rule fed to the translateMaterialPage boundary. */
export function makeWireRule(overrides: Partial<WireRule> = {}): WireRule {
  return {
    disposition: "curbside_recycle",
    accepted_status: "accepted",
    preparation_steps: [],
    exceptions: [],
    warnings: [],
    ...overrides,
  };
}
