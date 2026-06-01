/**
 * Material page ACL -- types, translators, and fetch helper for the
 * material detail page.
 *
 * Dependency direction: citation <- jurisdiction <- material (acyclic).
 * A material page is within a jurisdiction; this module imports from
 * jurisdiction.ts, never the reverse.
 *
 * Components import from lib/api/index.ts; this module is internal
 * to the ACL layer.
 *
 * Per architecture.md § Frontend: Smart-UI rejection and
 * ddd/integrating-bounded-contexts.md Principle 5.
 */

import "server-only";
import type { components } from "./types";
import { apiClient } from "./client";
import { type Citation, translateCitation } from "./citation";
import { type Jurisdiction, translateJurisdiction } from "./jurisdiction";

type WireMaterialDetail = components["schemas"]["MaterialDetailWire"];
type WireRule = components["schemas"]["RuleWire"];
type WireMaterialPage = components["schemas"]["MaterialPageWire"];

// -- Presentation-context types -----------------------------------------------

export interface MaterialDetail {
  id: string;
  slug: string;
  canonicalName: string;
}

export interface Rule {
  disposition: string;
  acceptedStatus: string;
  preparationSteps: string[];
  exceptions: string[];
  warnings: string[];
}

export interface MaterialPage {
  jurisdiction: Jurisdiction;
  material: MaterialDetail;
  rule: Rule;
  citations: Citation[];
}

// -- Translation functions ----------------------------------------------------

function translateMaterialDetail(w: WireMaterialDetail): MaterialDetail {
  return {
    id: w.id,
    slug: w.slug,
    canonicalName: w.canonical_name,
  };
}

function translateRule(w: WireRule): Rule {
  return {
    disposition: w.disposition,
    acceptedStatus: w.accepted_status,
    preparationSteps: w.preparation_steps,
    exceptions: w.exceptions,
    warnings: w.warnings,
  };
}

export function translateMaterialPage(w: WireMaterialPage): MaterialPage {
  return {
    jurisdiction: translateJurisdiction(w.jurisdiction),
    material: translateMaterialDetail(w.material),
    rule: translateRule(w.rule),
    citations: w.citations.map(translateCitation),
  };
}

// -- Fetch helper -------------------------------------------------------------

export async function fetchMaterialPage(
  jSlug: string,
  mSlug: string,
): Promise<MaterialPage | null> {
  const { data, error, response } = await apiClient.GET(
    "/pages/jurisdiction/{j_slug}/material/{m_slug}",
    { params: { path: { j_slug: jSlug, m_slug: mSlug } } },
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok || error || !data) {
    throw new Error(
      `fetchMaterialPage(${jSlug}, ${mSlug}): HTTP ${response.status}`,
    );
  }

  return translateMaterialPage(data);
}
