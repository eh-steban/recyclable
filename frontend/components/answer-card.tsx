import type { Answer, Citation } from "@/lib/api";

interface AnswerCardProps {
  answer: Answer;
}

export function AnswerCard({ answer }: AnswerCardProps) {
  const {
    shortAnswer,
    recommendedAction,
    preparationSteps,
    doNotDo,
    citations,
    confidence,
    clarifyingQuestion,
    refusalReason,
    jurisdiction,
  } = answer;

  if (clarifyingQuestion !== null) {
    return (
      <article className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <ShortAnswerBadge shortAnswer={shortAnswer} />
        <p className="mt-4 text-gray-700">{clarifyingQuestion}</p>
      </article>
    );
  }

  if (refusalReason === "out_of_jurisdiction" && jurisdiction.id === null) {
    return (
      <article className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <ShortAnswerBadge shortAnswer={shortAnswer} />
        <p className="mt-4 text-gray-600">
          {jurisdiction.name} is not currently supported. We only have recycling
          rules for jurisdictions in our knowledge base.
        </p>
      </article>
    );
  }

  if (shortAnswer === "unknown") {
    return (
      <article className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <ShortAnswerBadge shortAnswer={shortAnswer} />
        <p className="mt-4 text-gray-600">
          {recommendedAction ||
            "No verified recycling rule was found for this question."}
        </p>
      </article>
    );
  }

  return (
    <article className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center gap-3">
        <ShortAnswerBadge shortAnswer={shortAnswer} />
        <ConfidenceBadge confidence={confidence} />
      </div>

      <p className="mt-4 text-gray-800">{recommendedAction}</p>

      {preparationSteps.length > 0 && (
        <section className="mt-6">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
            Preparation steps
          </h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-gray-700">
            {preparationSteps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ul>
        </section>
      )}

      {doNotDo.length > 0 && (
        <section className="mt-6">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
            Do not
          </h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-red-700">
            {doNotDo.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </section>
      )}

      {citations.length > 0 && <CitationsList citations={citations} />}
    </article>
  );
}

function ShortAnswerBadge({ shortAnswer }: { shortAnswer: string }) {
  const colors: Record<string, string> = {
    yes: "bg-green-100 text-green-800",
    no: "bg-red-100 text-red-800",
    conditional: "bg-yellow-100 text-yellow-800",
    unknown: "bg-gray-100 text-gray-700",
  };
  const cls = colors[shortAnswer] ?? colors["unknown"];
  return (
    <span className={`rounded px-2 py-0.5 text-sm font-medium ${cls}`}>
      {shortAnswer}
    </span>
  );
}

function ConfidenceBadge({ confidence }: { confidence: string }) {
  const colors: Record<string, string> = {
    high: "bg-blue-100 text-blue-800",
    medium: "bg-indigo-100 text-indigo-800",
    low: "bg-orange-100 text-orange-800",
  };
  const cls = colors[confidence] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`rounded px-2 py-0.5 text-sm font-medium ${cls}`}>
      {confidence}
    </span>
  );
}

function CitationsList({ citations }: { citations: Citation[] }) {
  return (
    <section className="mt-8 border-t border-gray-200 pt-6">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
        Sources
      </h2>
      <ul className="mt-3 space-y-4">
        {citations.map((c, i) => (
          <li key={i}>
            <a
              href={c.url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-blue-600 hover:underline"
            >
              {c.title}
            </a>
            {c.quote && (
              <blockquote className="mt-1 border-l-2 border-gray-300 pl-3 text-sm italic text-gray-600">
                {c.quote}
              </blockquote>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
