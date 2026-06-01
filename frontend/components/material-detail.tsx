import type { MaterialPage } from "@/lib/api";

interface MaterialDetailProps {
  page: MaterialPage;
}

/**
 * Full material detail body -- renders all rule fields plus citations.
 */
export function MaterialDetail({ page }: MaterialDetailProps) {
  const { material, rule, citations } = page;

  return (
    <article className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-bold text-gray-900">
        {material.canonicalName}
      </h1>

      <div className="mt-4 flex flex-wrap gap-2">
        <StatusBadge status={rule.acceptedStatus} />
        <DispositionBadge disposition={rule.disposition} />
      </div>

      {rule.preparationSteps.length > 0 && (
        <section className="mt-6">
          <h2 className="text-lg font-semibold text-gray-800">
            Preparation steps
          </h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-gray-700">
            {rule.preparationSteps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ul>
        </section>
      )}

      {rule.exceptions.length > 0 && (
        <section className="mt-6">
          <h2 className="text-lg font-semibold text-gray-800">Exceptions</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-gray-700">
            {rule.exceptions.map((exc, i) => (
              <li key={i}>{exc}</li>
            ))}
          </ul>
        </section>
      )}

      {rule.warnings.length > 0 && (
        <section className="mt-6">
          <h2 className="text-lg font-semibold text-gray-800">Warnings</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-yellow-700">
            {rule.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </section>
      )}

      {citations.length > 0 && (
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
      )}
    </article>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    accepted: "bg-green-100 text-green-800",
    rejected: "bg-red-100 text-red-800",
    conditional: "bg-yellow-100 text-yellow-800",
    unknown: "bg-gray-100 text-gray-700",
  };
  const cls = colors[status] ?? colors["unknown"];
  return (
    <span className={`rounded px-2 py-0.5 text-sm font-medium ${cls}`}>
      {status}
    </span>
  );
}

function DispositionBadge({ disposition }: { disposition: string }) {
  return (
    <span className="rounded bg-blue-100 px-2 py-0.5 text-sm font-medium text-blue-800">
      {disposition.replace(/_/g, " ")}
    </span>
  );
}
