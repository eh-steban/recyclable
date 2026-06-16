import { describe, it, expect } from "vitest";
import { translateCitation } from "@/lib/api/citation";
import {
  makeWireCitation,
  DENVER_RECYCLING_URL,
} from "@/tests/fixtures/citations";

describe("translateCitation quote handling", () => {
  it("preserves null quote as null (not undefined or the string 'null')", () => {
    const wire = makeWireCitation({ quote: null });
    const citation = translateCitation(wire);

    expect(citation.quote).toBeNull();
    expect(citation.quote).not.toBeUndefined();
    expect(citation.quote).not.toBe("null");
  });

  it("preserves a non-null quote string", () => {
    const wire = makeWireCitation({
      quote: "Aluminum cans are accepted curbside.",
    });
    const citation = translateCitation(wire);
    expect(citation.quote).toBe("Aluminum cans are accepted curbside.");
  });

  it("passes through title and url fields", () => {
    const wire = makeWireCitation({
      title: "Denver Recycling",
      url: DENVER_RECYCLING_URL,
      quote: null,
    });
    const citation = translateCitation(wire);
    expect(citation.title).toBe("Denver Recycling");
    expect(citation.url).toBe("https://www.denvergov.org/recycling");
  });
});
