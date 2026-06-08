/**
 * No `server-only` guard here: the presentation types (Answer,
 * JurisdictionRef, etc.) must be importable by client components
 * via `import type`. The fetch helper (fetchAsk) uses apiClient
 * which is server-only; it is called only from the Server Action
 * in app/ask/actions.ts, never from a client component at runtime.
 */

import { apiClient } from "./client";
import { type Citation, translateCitation } from "./citation";
import type { components } from "./types";

type WireAnswer = components["schemas"]["Answer"];

// -- Presentation-context types -------------------------------------------

export interface JurisdictionRef {
  id: string;
  name: string;
}

export interface UnresolvedJurisdiction {
  id: null;
  name: string;
}

/**
 * Translated presentation-context answer. All field names are
 * camelCase; wire snake_case fields are mapped here. Discriminate
 * on `jurisdiction.id !== null` before constructing any URL.
 */
export interface Answer {
  auditRecordId: string;
  /** 'yes' | 'no' | 'conditional' | 'unknown' */
  shortAnswer: string;
  recommendedAction: string;
  preparationSteps: string[];
  doNotDo: string[];
  citations: Citation[];
  /** 'high' | 'medium' | 'low' */
  confidence: string;
  clarifyingQuestion: string | null;
  /**
   * Non-null exactly when shortAnswer='unknown'.
   * 'out_of_jurisdiction' | 'no_evidence' | 'conflict_unresolved' | null
   */
  refusalReason: string | null;
  jurisdiction: JurisdictionRef | UnresolvedJurisdiction;
  dropoffOptions: Facility[];
}

export interface Facility {
  id: string;
  name: string;
  address: string;
}

export interface AskInput {
  query: string;
  location: string;
}

/** Discriminated-union result from fetchAsk. */
export type AskResult =
  | { ok: true; answer: Answer }
  | { ok: false; error: string };

// -- Translation ----------------------------------------------------------

function translateAnswer(w: WireAnswer): Answer {
  return {
    auditRecordId: w.audit_record_id,
    shortAnswer: w.short_answer,
    recommendedAction: w.recommended_action,
    preparationSteps: w.preparation_steps,
    doNotDo: w.do_not_do,
    citations: w.citations.map(translateCitation),
    confidence: w.confidence,
    clarifyingQuestion: w.clarifying_question,
    refusalReason: w.refusal_reason,
    jurisdiction: {
      id: w.jurisdiction.id,
      name: w.jurisdiction.name,
    },
    dropoffOptions: w.dropoff_options.map((f) => ({
      id: f.id,
      name: f.name,
      address: f.address,
    })),
  };
}

// -- Fetch helper ---------------------------------------------------------

export async function fetchAsk(input: AskInput): Promise<AskResult> {
  let response: Response;
  let data: WireAnswer | undefined;
  let error: unknown;

  try {
    const result = await apiClient.POST("/ask", {
      body: { query: input.query, location: input.location },
    });
    response = result.response;
    data = result.data as WireAnswer | undefined;
    error = result.error;
  } catch (err) {
    console.error("fetchAsk: network error", { message: String(err) });
    return { ok: false, error: "network_error" };
  }

  if (response.status === 200 && data) {
    return { ok: true, answer: translateAnswer(data) };
  }

  console.error("fetchAsk: non-200 response", {
    status: response.status,
  });
  return {
    ok: false,
    error: (error as { error?: string })?.error ?? "internal_error",
  };
}
