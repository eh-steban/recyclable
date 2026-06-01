import { describe, it, expect } from "vitest";
import { translateMaterialPage } from "@/lib/api/material";

function makeWireJurisdiction() {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    name: "Denver, CO",
    slug: "denver-co-us",
  };
}

function makeWireRule() {
  return {
    disposition: "curbside_recycle",
    accepted_status: "accepted",
    preparation_steps: ["Rinse"],
    exceptions: [],
    warnings: [],
  };
}

function makeWireMaterialDetail() {
  return {
    id: "00000000-0000-0000-0000-000000000002",
    slug: "aluminum-cans",
    canonical_name: "Aluminum Cans",
  };
}

function makeWireCitation(quote?: string | null) {
  return {
    title: "Denver Recycling",
    url: "https://www.denvergov.org/recycling",
    quote: quote,
  };
}

// -- translateMaterialPage ----------------------------------------------------

describe("translateMaterialPage", () => {
  it("maps material snake_case to camelCase", () => {
    const wire = {
      jurisdiction: makeWireJurisdiction(),
      material: makeWireMaterialDetail(),
      rule: makeWireRule(),
      citations: [],
    };
    const page = translateMaterialPage(wire);

    expect(page.material.canonicalName).toBe("Aluminum Cans");
    expect(page.material.slug).toBe("aluminum-cans");
  });

  it("maps rule snake_case to camelCase", () => {
    const wire = {
      jurisdiction: makeWireJurisdiction(),
      material: makeWireMaterialDetail(),
      rule: makeWireRule(),
      citations: [],
    };
    const page = translateMaterialPage(wire);

    expect(page.rule.acceptedStatus).toBe("accepted");
    expect(page.rule.preparationSteps).toEqual(["Rinse"]);
    expect(page.rule.disposition).toBe("curbside_recycle");
  });

  it("translates citations array", () => {
    const wire = {
      jurisdiction: makeWireJurisdiction(),
      material: makeWireMaterialDetail(),
      rule: makeWireRule(),
      citations: [makeWireCitation("Some quote")],
    };
    const page = translateMaterialPage(wire);

    expect(page.citations).toHaveLength(1);
    expect(page.citations[0].quote).toBe("Some quote");
  });

  it("produces empty citations array when wire citations is empty", () => {
    const wire = {
      jurisdiction: makeWireJurisdiction(),
      material: makeWireMaterialDetail(),
      rule: makeWireRule(),
      citations: [],
    };
    const page = translateMaterialPage(wire);
    expect(page.citations).toHaveLength(0);
  });
});
