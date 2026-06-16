import type { components } from "@/lib/api/types";
import type { Citation } from "@/lib/api/citation";

type WireCitation = components["schemas"]["CitationWire"];

export const DENVER_RECYCLING_URL = "https://www.denvergov.org/recycling";

export function makeCitation(overrides: Partial<Citation> = {}): Citation {
  return {
    title: "Denver Recycling -- What to Recycle",
    url: DENVER_RECYCLING_URL,
    quote: "Aluminum cans are accepted curbside.",
    ...overrides,
  };
}

export function makeWireCitation(
  overrides: Partial<WireCitation> = {},
): WireCitation {
  return {
    title: "Denver Recycling",
    url: DENVER_RECYCLING_URL,
    quote: null,
    ...overrides,
  };
}
