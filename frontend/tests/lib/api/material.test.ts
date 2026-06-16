import { describe, it, expect } from "vitest";
import { translateMaterialPage } from "@/lib/api/material";
import { makeWireJurisdiction } from "@/tests/fixtures/jurisdictions";
import {
  makeWireMaterialDetail,
  makeWireRule,
} from "@/tests/fixtures/materials";
import { makeWireCitation } from "@/tests/fixtures/citations";

// -- translateMaterialPage ----------------------------------------------------

describe("translateMaterialPage", () => {
  it("maps material snake_case to camelCase", () => {
    const wire = {
      jurisdiction: makeWireJurisdiction(),
      material: makeWireMaterialDetail({
        slug: "aluminum-cans",
        canonical_name: "Aluminum Cans",
      }),
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
      rule: makeWireRule({
        disposition: "curbside_recycle",
        accepted_status: "accepted",
        preparation_steps: ["Rinse"],
      }),
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
      citations: [makeWireCitation({ quote: "Some quote" })],
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
