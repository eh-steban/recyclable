import Link from "next/link";
import type { MaterialSummary } from "@/lib/api";

interface MaterialRowProps {
  material: MaterialSummary;
  href: string;
}

/**
 * One row in the jurisdiction landing page material list.
 */
export function MaterialRow({ material, href }: MaterialRowProps) {
  const { canonicalName, acceptedStatus, needsPreparation, citation } =
    material;

  return (
    <li className="flex flex-col gap-1 border-b border-gray-100 py-4 last:border-0">
      <div className="flex items-center gap-3">
        <Link href={href} className="font-medium text-gray-900 hover:underline">
          {canonicalName}
        </Link>
        <StatusBadge status={acceptedStatus} />
        {needsPreparation && (
          <span className="rounded bg-yellow-100 px-2 py-0.5 text-xs text-yellow-800">
            prep needed
          </span>
        )}
      </div>
      <a
        href={citation.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-sm text-blue-600 hover:underline"
      >
        {citation.title}
      </a>
    </li>
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
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${cls}`}>
      {status}
    </span>
  );
}
