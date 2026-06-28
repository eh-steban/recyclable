import { describe, it, expect, vi, beforeEach } from "vitest";

const { mockGET } = vi.hoisted(() => ({ mockGET: vi.fn() }));
vi.mock("@/lib/api/client", () => ({
  apiClient: { GET: mockGET },
}));

import { fetchMaterialPage, translateMaterialPage } from "@/lib/api/material";
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

// -- fetchMaterialPage --------------------------------------------------------

// Guards INV-OPS-006.
describe("fetchMaterialPage", () => {
  beforeEach(() => {
    mockGET.mockReset();
  });

  it("returns the translated page on a 200 response", async () => {
    mockGET.mockResolvedValue({
      data: {
        jurisdiction: makeWireJurisdiction(),
        material: makeWireMaterialDetail(),
        rule: makeWireRule(),
        citations: [],
      },
      error: undefined,
      response: { ok: true, status: 200 },
    });

    const page = await fetchMaterialPage("denver-co-us", "aluminum-cans");

    expect(page?.material.slug).toBe("aluminum-cans");
  });

  it("returns null on a 404 (material genuinely absent)", async () => {
    mockGET.mockResolvedValue({
      data: undefined,
      error: { detail: "not found" },
      response: { ok: false, status: 404 },
    });

    expect(await fetchMaterialPage("denver-co-us", "unobtainium")).toBeNull();
  });

  it("throws on a 5xx so the build fails instead of caching a false 404", async () => {
    mockGET.mockResolvedValue({
      data: undefined,
      error: { detail: "boom" },
      response: { ok: false, status: 500 },
    });

    await expect(
      fetchMaterialPage("denver-co-us", "aluminum-cans"),
    ).rejects.toThrow(/HTTP 500/);
  });

  it("throws when the response is ok but the body is missing", async () => {
    mockGET.mockResolvedValue({
      data: undefined,
      error: undefined,
      response: { ok: true, status: 200 },
    });

    await expect(
      fetchMaterialPage("denver-co-us", "aluminum-cans"),
    ).rejects.toThrow(/HTTP 200/);
  });

  it("propagates a network failure so the build fails", async () => {
    mockGET.mockRejectedValue(new TypeError("Network request failed"));

    await expect(
      fetchMaterialPage("denver-co-us", "aluminum-cans"),
    ).rejects.toThrow("Network request failed");
  });
});
