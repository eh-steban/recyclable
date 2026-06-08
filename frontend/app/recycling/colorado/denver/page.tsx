import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { DENVER_SLUG, fetchJurisdictionPage } from "@/lib/api";
import { MaterialRow } from "@/components/material-row";

export const dynamic = "force-static";
export const revalidate = false;

export const metadata: Metadata = {
  title: "Denver, CO Recycling Guide -- Recyclable",
  description:
    "What you can and cannot recycle curbside in Denver, CO." +
    " Source-cited rules from the City of Denver.",
};

export default async function DenverJurisdictionPage() {
  const page = await fetchJurisdictionPage(DENVER_SLUG);

  if (!page) notFound();

  const { jurisdiction, materials } = page;

  return (
    <main className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-bold text-gray-900">
        {jurisdiction.name} Recycling Guide
      </h1>
      <p className="mt-2 text-sm text-gray-500">
        {materials.length} material
        {materials.length === 1 ? "" : "s"} with active rules
      </p>

      <ul className="mt-6">
        {materials.map((m) => (
          <MaterialRow
            key={m.id}
            material={m}
            href={`/recycling/colorado/denver/${m.slug}`}
          />
        ))}
      </ul>
    </main>
  );
}
