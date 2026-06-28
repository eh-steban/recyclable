import type { Answer } from "@/lib/api/ask";
import { makeCitation } from "./citations";

export function makeAnswer(overrides: Partial<Answer> = {}): Answer {
  return {
    auditRecordId: "00000000-0000-0000-0000-000000000001",
    shortAnswer: "yes",
    recommendedAction: "Place in your blue recycling cart.",
    preparationSteps: [],
    doNotDo: [],
    citations: [makeCitation()],
    confidence: "high",
    clarifyingQuestion: null,
    refusalReason: null,
    jurisdiction: {
      id: "00000000-0000-0000-0000-000000000002",
      name: "Denver, CO",
    },
    dropoffOptions: [],
    ...overrides,
  };
}

/** Successful AskResult wrapping a presentation answer (AskBox tests). */
export function makeOkAnswer(overrides: Partial<Answer> = {}): {
  ok: true;
  answer: Answer;
} {
  return { ok: true, answer: makeAnswer(overrides) };
}
