import { describe, it, expect } from "vitest";
import { translateCitation } from "@/lib/api/citation";

function makeWireCitation(quote?: string | null) {
  return {
    title: "Denver Recycling",
    url: "https://www.denvergov.org/recycling",
    quote: quote,
  };
}

describe("translateCitation quote handling", () => {
  it("preserves null quote as null (not undefined or the string 'null')", () => {
    const wire = makeWireCitation(null);
    const citation = translateCitation(wire);

    expect(citation.quote).toBeNull();
    expect(citation.quote).not.toBeUndefined();
    expect(citation.quote).not.toBe("null");
  });

  it("preserves a non-null quote string", () => {
    const wire = makeWireCitation("Aluminum cans are accepted curbside.");
    const citation = translateCitation(wire);
    expect(citation.quote).toBe("Aluminum cans are accepted curbside.");
  });

  it("passes through title and url fields", () => {
    const wire = makeWireCitation(null);
    const citation = translateCitation(wire);
    expect(citation.title).toBe("Denver Recycling");
    expect(citation.url).toBe("https://www.denvergov.org/recycling");
  });
});
