/**
 * Jurisdiction page ACL -- types, translators, and fetch helper for
 * the jurisdiction landing page.
 *
 * Components import from lib/api/index.ts; this module is internal
 * to the ACL layer.
 */

import "server-only";
import type { components } from "./types";
import { apiClient } from "./client";
import { type Citation, translateCitation } from "./citation";

type WireJurisdiction = components["schemas"]["JurisdictionWire"];
type WireMaterialSummary = components["schemas"]["MaterialSummaryWire"];
type WireJurisdictionPage = components["schemas"]["JurisdictionPageWire"];

// -- Presentation-context types -----------------------------------------------

export interface Jurisdiction {
  id: string;
  name: string;
  slug: string;
}

export interface MaterialSummary {
  id: string;
  slug: string;
  canonicalName: string;
  acceptedStatus: string;
  needsPreparation: boolean;
  citation: Citation;
}

export interface JurisdictionPage {
  jurisdiction: Jurisdiction;
  materials: MaterialSummary[];
}

export const DENVER_SLUG = "denver-co-us" as const;

// -- Translation functions ----------------------------------------------------

export function translateJurisdiction(w: WireJurisdiction): Jurisdiction {
  return { id: w.id, name: w.name, slug: w.slug };
}

function translateMaterialSummary(w: WireMaterialSummary): MaterialSummary {
  return {
    id: w.id,
    slug: w.slug,
    canonicalName: w.canonical_name,
    acceptedStatus: w.accepted_status,
    needsPreparation: w.needs_preparation,
    citation: translateCitation(w.citation),
  };
}

export function translateJurisdictionPage(
  w: WireJurisdictionPage,
): JurisdictionPage {
  return {
    jurisdiction: translateJurisdiction(w.jurisdiction),
    materials: w.materials.map(translateMaterialSummary),
  };
}

// -- Fetch helper -------------------------------------------------------------

export async function fetchJurisdictionPage(
  slug: string,
): Promise<JurisdictionPage | null> {
  const { data, error, response } = await apiClient.GET(
    "/pages/jurisdiction/{slug}",
    { params: { path: { slug } } },
  );

  if (response.status === 404) {
    return null;
  }

  if (!response.ok || error || !data) {
    throw new Error(`fetchJurisdictionPage(${slug}): HTTP ${response.status}`);
  }

  return translateJurisdictionPage(data);
}
