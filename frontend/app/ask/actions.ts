"use server";

import { fetchAsk, type AskInput, type AskResult } from "@/lib/api/ask";

export async function submitAsk(input: AskInput): Promise<AskResult> {
  return fetchAsk(input);
}
