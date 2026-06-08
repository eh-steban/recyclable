import { describe, it, expect } from "vitest";
import { translateJurisdictionPage, DENVER_SLUG } from "@/lib/api/jurisdiction";

function makeWireJurisdiction() {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    name: "Denver, CO",
    slug: "denver-co-us",
  };
}

function makeWireMaterialSummary() {
  return {
    id: "00000000-0000-0000-0000-000000000002",
    slug: "aluminum-cans",
    canonical_name: "Aluminum Cans",
    accepted_status: "accepted",
    needs_preparation: false,
    citation: {
      title: "Denver Recycling",
      url: "https://www.denvergov.org/recycling",
      quote: null as string | null | undefined,
    },
  };
}

// -- translateJurisdictionPage ------------------------------------------------

describe("translateJurisdictionPage", () => {
  it("maps snake_case wire fields to camelCase presentation fields", () => {
    const wire = {
      jurisdiction: makeWireJurisdiction(),
      materials: [makeWireMaterialSummary()],
    };
    const page = translateJurisdictionPage(wire);

    const m = page.materials[0];
    expect(m.canonicalName).toBe("Aluminum Cans");
    expect(m.acceptedStatus).toBe("accepted");
    expect(m.needsPreparation).toBe(false);
  });

  it("passes through jurisdiction identity fields", () => {
    const wire = {
      jurisdiction: makeWireJurisdiction(),
      materials: [],
    };
    const page = translateJurisdictionPage(wire);

    expect(page.jurisdiction.id).toBe("00000000-0000-0000-0000-000000000001");
    expect(page.jurisdiction.name).toBe("Denver, CO");
    expect(page.jurisdiction.slug).toBe("denver-co-us");
  });

  it("maps citation fields inside material summary", () => {
    const wire = {
      jurisdiction: makeWireJurisdiction(),
      materials: [makeWireMaterialSummary()],
    };
    const page = translateJurisdictionPage(wire);

    const { citation } = page.materials[0];
    expect(citation.title).toBe("Denver Recycling");
    expect(citation.url).toBe("https://www.denvergov.org/recycling");
    expect(citation.quote).toBeNull();
  });
});

// -- DENVER_SLUG pin ----------------------------------------------------------

describe("DENVER_SLUG", () => {
  it("equals the reconciled slug 'denver-co-us'", () => {
    expect(DENVER_SLUG).toBe("denver-co-us");
  });
});
