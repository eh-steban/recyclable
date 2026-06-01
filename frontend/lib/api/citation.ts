/**
 * Citation -- shared value type used by both the jurisdiction landing
 * page and the material detail page (and Phase 8's answer card).
 *
 * Pure module: no server-only import needed because Citation is a
 * presentation-context type consumed by components, not a server-side
 * fetch helper.
 *
 * Per architecture.md § Frontend: Smart-UI rejection and
 * ddd/integrating-bounded-contexts.md Principle 5.
 */

import type { components } from "./types";

type WireCitation = components["schemas"]["CitationWire"];

export interface Citation {
  title: string;
  url: string;
  quote?: string | null;
}

export function translateCitation(w: WireCitation): Citation {
  return { title: w.title, url: w.url, quote: w.quote };
}
