import { describe, it, expect, vi, beforeEach } from "vitest";

const { mockGET } = vi.hoisted(() => ({ mockGET: vi.fn() }));
vi.mock("@/lib/api/client", () => ({
  apiClient: { GET: mockGET },
}));

import {
  fetchJurisdictionPage,
  translateJurisdictionPage,
  DENVER_SLUG,
} from "@/lib/api/jurisdiction";

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

// -- fetchJurisdictionPage ----------------------------------------------------

// Guards INV-OPS-006.
describe("fetchJurisdictionPage", () => {
  beforeEach(() => {
    mockGET.mockReset();
  });

  it("returns the translated page on a 200 response", async () => {
    mockGET.mockResolvedValue({
      data: {
        jurisdiction: makeWireJurisdiction(),
        materials: [makeWireMaterialSummary()],
      },
      error: undefined,
      response: { ok: true, status: 200 },
    });

    const page = await fetchJurisdictionPage("denver-co-us");

    expect(page?.jurisdiction.slug).toBe("denver-co-us");
  });

  it("returns null on a 404 (jurisdiction genuinely absent)", async () => {
    mockGET.mockResolvedValue({
      data: undefined,
      error: { detail: "not found" },
      response: { ok: false, status: 404 },
    });

    expect(await fetchJurisdictionPage("atlantis")).toBeNull();
  });

  it("throws on a 5xx so the build fails instead of caching a false 404", async () => {
    mockGET.mockResolvedValue({
      data: undefined,
      error: { detail: "boom" },
      response: { ok: false, status: 503 },
    });

    await expect(fetchJurisdictionPage("denver-co-us")).rejects.toThrow(
      /HTTP 503/,
    );
  });

  it("throws when the response is ok but the body is missing", async () => {
    mockGET.mockResolvedValue({
      data: undefined,
      error: undefined,
      response: { ok: true, status: 200 },
    });

    await expect(fetchJurisdictionPage("denver-co-us")).rejects.toThrow(
      /HTTP 200/,
    );
  });

  it("propagates a network failure so the build fails", async () => {
    mockGET.mockRejectedValue(new TypeError("Network request failed"));

    await expect(fetchJurisdictionPage("denver-co-us")).rejects.toThrow(
      "Network request failed",
    );
  });
});
