import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import {
  DENVER_SLUG,
  fetchJurisdictionPage,
  fetchMaterialPage,
} from "@/lib/api";
import { MaterialDetail } from "@/components/material-detail";

export const dynamicParams = false;
export const revalidate = false;

export async function generateStaticParams() {
  const page = await fetchJurisdictionPage(DENVER_SLUG);
  if (!page) {
    throw new Error(
      `generateStaticParams: jurisdiction ${DENVER_SLUG} not found`,
    );
  }
  return page.materials.map((m) => ({ material: m.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ material: string }>;
}): Promise<Metadata> {
  const { material: mSlug } = await params;
  const page = await fetchMaterialPage(DENVER_SLUG, mSlug);
  if (!page) {
    return { title: "Not found -- Recyclable" };
  }
  return {
    title: `${page.material.canonicalName} in Denver, CO` + " -- Recyclable",
    description:
      `Recycling rules for ${page.material.canonicalName}` +
      ` in Denver, CO. Accepted status: ${page.rule.acceptedStatus}.`,
  };
}

export default async function DenverMaterialPage({
  params,
}: {
  params: Promise<{ material: string }>;
}) {
  const { material: mSlug } = await params;
  const page = await fetchMaterialPage(DENVER_SLUG, mSlug);

  if (!page) {
    notFound();
  }

  return (
    <>
      <nav className="border-b border-gray-100">
        <div className="mx-auto max-w-2xl px-4 py-3 text-sm text-gray-500">
          <Link
            href="/recycling/colorado/denver"
            className="hover:text-gray-700"
          >
            Denver recycling guide
          </Link>
          {" / "}
          <span className="text-gray-900">{page.material.canonicalName}</span>
        </div>
      </nav>
      <MaterialDetail page={page} />
    </>
  );
}
