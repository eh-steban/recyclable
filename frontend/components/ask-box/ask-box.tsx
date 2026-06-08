"use client";

import { useState, type SubmitEvent } from "react";
import { submitAsk } from "@/app/ask/actions";
import { AnswerCard } from "@/components/answer-card";
import type { Answer } from "@/lib/api";

export function AskBox() {
  const [location, setLocation] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  async function handleSubmit(e: SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setAnswer(null);
    setErrorMsg(null);

    const result = await submitAsk({ query, location });

    setLoading(false);

    if (result.ok) {
      setAnswer(result.answer);
    } else {
      setErrorMsg("Something went wrong, please try again.");
    }
  }

  return (
    <div>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="ask-location"
            className="block text-sm font-medium text-gray-700"
          >
            City
          </label>
          <input
            id="ask-location"
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="City (Denver supported)"
            required
            className={[
              "mt-1 block w-full rounded-md border border-gray-300 px-3 py-2",
              "text-sm shadow-sm focus:border-blue-500 focus:outline-none",
              "focus:ring-1 focus:ring-blue-500",
            ].join(" ")}
          />
        </div>

        <div>
          <label
            htmlFor="ask-query"
            className="block text-sm font-medium text-gray-700"
          >
            Question
          </label>
          <textarea
            id="ask-query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. Can I recycle cardboard in Denver?"
            required
            rows={3}
            className={[
              "mt-1 block w-full rounded-md border border-gray-300 px-3 py-2",
              "text-sm shadow-sm focus:border-blue-500 focus:outline-none",
              "focus:ring-1 focus:ring-blue-500",
            ].join(" ")}
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className={[
            "inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2",
            "text-sm font-medium text-white shadow-sm",
            "hover:bg-blue-700 focus:outline-none focus:ring-2",
            "focus:ring-blue-500 focus:ring-offset-2",
            "disabled:opacity-50 disabled:cursor-not-allowed",
          ].join(" ")}
        >
          {loading && <Spinner />}
          {loading ? "Checking..." : "Ask"}
        </button>
      </form>

      {errorMsg && (
        <p
          role="alert"
          className="mt-6 rounded-md bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {errorMsg}
        </p>
      )}

      {answer && (
        <div className="mt-8">
          <AnswerCard answer={answer} />
        </div>
      )}
    </div>
  );
}

function Spinner() {
  return (
    <svg
      className="h-4 w-4 animate-spin"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}
