import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MaterialRow } from "@/components/material-row";
import { makeMaterialSummary } from "@/tests/fixtures/materials";
import { makeCitation, DENVER_RECYCLING_URL } from "@/tests/fixtures/citations";

const aluminumCans = makeMaterialSummary({
  canonicalName: "Aluminum Cans",
  acceptedStatus: "accepted",
  needsPreparation: false,
  citation: makeCitation({
    title: "Denver Recycling -- What to Recycle",
    url: DENVER_RECYCLING_URL,
    quote: null,
  }),
});

const HREF = "/recycling/colorado/denver/aluminum-cans";

describe("MaterialRow", () => {
  it("renders the canonical name", () => {
    render(<MaterialRow material={aluminumCans} href={HREF} />);
    expect(screen.getByText("Aluminum Cans")).toBeInTheDocument();
  });

  it("renders the accepted_status badge", () => {
    render(<MaterialRow material={aluminumCans} href={HREF} />);
    expect(screen.getByText("accepted")).toBeInTheDocument();
  });

  it("renders the material name as a link to the detail page", () => {
    render(<MaterialRow material={aluminumCans} href={HREF} />);
    const nameLink = screen.getByRole("link", { name: "Aluminum Cans" });
    expect(nameLink).toHaveAttribute("href", HREF);
  });

  it("renders the citation as a separate link with citation.url", () => {
    render(<MaterialRow material={aluminumCans} href={HREF} />);
    const citationLink = screen.getByRole("link", {
      name: "Denver Recycling -- What to Recycle",
    });
    expect(citationLink).toHaveAttribute(
      "href",
      "https://www.denvergov.org/recycling",
    );
  });

  it("citation link and name link are not nested -- two sibling links", () => {
    render(<MaterialRow material={aluminumCans} href={HREF} />);
    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute("href", HREF);
    expect(links[1]).toHaveAttribute(
      "href",
      "https://www.denvergov.org/recycling",
    );
  });

  it("renders the citation title", () => {
    render(<MaterialRow material={aluminumCans} href={HREF} />);
    expect(
      screen.getByText("Denver Recycling -- What to Recycle"),
    ).toBeInTheDocument();
  });

  it("does not show prep-needed badge when needsPreparation is false", () => {
    render(<MaterialRow material={aluminumCans} href={HREF} />);
    expect(screen.queryByText("prep needed")).not.toBeInTheDocument();
  });

  it("shows prep-needed badge when needsPreparation is true", () => {
    const prepMaterial = { ...aluminumCans, needsPreparation: true };
    render(<MaterialRow material={prepMaterial} href={HREF} />);
    expect(screen.getByText("prep needed")).toBeInTheDocument();
  });

  it("renders rejected status with correct badge text", () => {
    const rejectedMaterial = {
      ...aluminumCans,
      canonicalName: "Plastic Bags",
      slug: "plastic-bags",
      acceptedStatus: "rejected",
    };
    render(
      <MaterialRow
        material={rejectedMaterial}
        href="/recycling/colorado/denver/plastic-bags"
      />,
    );
    expect(screen.getByText("rejected")).toBeInTheDocument();
    expect(screen.getByText("Plastic Bags")).toBeInTheDocument();
  });

  it("renders conditional status badge", () => {
    const conditionalMaterial = {
      ...aluminumCans,
      canonicalName: "Motor Oil",
      slug: "motor-oil",
      acceptedStatus: "conditional",
    };
    render(
      <MaterialRow
        material={conditionalMaterial}
        href="/recycling/colorado/denver/motor-oil"
      />,
    );
    expect(screen.getByText("conditional")).toBeInTheDocument();
    expect(screen.getByText("Motor Oil")).toBeInTheDocument();
  });
});
