import type { Jurisdiction } from "@/lib/api/jurisdiction";
import type { components } from "@/lib/api/types";

type WireJurisdiction = components["schemas"]["JurisdictionWire"];

export const DENVER_JURISDICTION_ID = "00000000-0000-0000-0000-000000000001";
export const DENVER_NAME = "Denver, CO";
export const DENVER_SLUG = "denver-co-us";

export function makeJurisdiction(
  overrides: Partial<Jurisdiction> = {},
): Jurisdiction {
  return {
    id: DENVER_JURISDICTION_ID,
    name: DENVER_NAME,
    slug: DENVER_SLUG,
    ...overrides,
  };
}

/** Wire-shape jurisdiction fed to the translateJurisdictionPage boundary. */
export function makeWireJurisdiction(
  overrides: Partial<WireJurisdiction> = {},
): WireJurisdiction {
  return {
    id: DENVER_JURISDICTION_ID,
    name: DENVER_NAME,
    slug: DENVER_SLUG,
    ...overrides,
  };
}
