import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MaterialDetail } from "@/components/material-detail";
import type { MaterialPage } from "@/lib/api";

const jurisdiction = {
  id: "00000000-0000-0000-0000-000000000001",
  name: "Denver, CO",
  slug: "denver-co-us",
};

const material = {
  id: "00000000-0000-0000-0000-000000000002",
  slug: "aluminum-cans",
  canonicalName: "Aluminum Cans",
};

const citation = {
  title: "Denver Recycling -- What to Recycle",
  url: "https://www.denvergov.org/recycling",
  quote: "Aluminum cans are accepted curbside.",
};

function makePage(overrides: Partial<MaterialPage> = {}): MaterialPage {
  return {
    jurisdiction,
    material,
    rule: {
      disposition: "curbside_recycle",
      acceptedStatus: "accepted",
      preparationSteps: [],
      exceptions: [],
      warnings: [],
    },
    citations: [citation],
    ...overrides,
  };
}

describe("MaterialDetail -- status badges", () => {
  it("renders accepted badge", () => {
    render(<MaterialDetail page={makePage()} />);
    expect(screen.getByText("accepted")).toBeInTheDocument();
  });

  it("renders rejected badge", () => {
    render(
      <MaterialDetail
        page={makePage({
          rule: {
            disposition: "landfill",
            acceptedStatus: "rejected",
            preparationSteps: [],
            exceptions: [],
            warnings: [],
          },
        })}
      />,
    );
    expect(screen.getByText("rejected")).toBeInTheDocument();
  });

  it("renders conditional badge", () => {
    render(
      <MaterialDetail
        page={makePage({
          rule: {
            disposition: "drop_off",
            acceptedStatus: "conditional",
            preparationSteps: [],
            exceptions: [],
            warnings: [],
          },
        })}
      />,
    );
    expect(screen.getByText("conditional")).toBeInTheDocument();
  });
});

describe("MaterialDetail -- disposition transform", () => {
  it("transforms curbside_recycle to 'curbside recycle'", () => {
    render(<MaterialDetail page={makePage()} />);
    expect(screen.getByText("curbside recycle")).toBeInTheDocument();
  });

  it("transforms drop_off to 'drop off'", () => {
    render(
      <MaterialDetail
        page={makePage({
          rule: {
            disposition: "drop_off",
            acceptedStatus: "conditional",
            preparationSteps: [],
            exceptions: [],
            warnings: [],
          },
        })}
      />,
    );
    expect(screen.getByText("drop off")).toBeInTheDocument();
  });
});

describe("MaterialDetail -- empty arrays render no section", () => {
  it("renders no Preparation steps section when array is empty", () => {
    render(<MaterialDetail page={makePage()} />);
    expect(screen.queryByText("Preparation steps")).not.toBeInTheDocument();
  });

  it("renders no Exceptions section when array is empty", () => {
    render(<MaterialDetail page={makePage()} />);
    expect(screen.queryByText("Exceptions")).not.toBeInTheDocument();
  });

  it("renders no Warnings section when array is empty", () => {
    render(<MaterialDetail page={makePage()} />);
    expect(screen.queryByText("Warnings")).not.toBeInTheDocument();
  });
});

describe("MaterialDetail -- non-empty arrays render their items", () => {
  it("renders preparation steps when present", () => {
    render(
      <MaterialDetail
        page={makePage({
          rule: {
            disposition: "curbside_recycle",
            acceptedStatus: "accepted",
            preparationSteps: ["Rinse the can", "Remove the lid"],
            exceptions: [],
            warnings: [],
          },
        })}
      />,
    );
    expect(screen.getByText("Preparation steps")).toBeInTheDocument();
    expect(screen.getByText("Rinse the can")).toBeInTheDocument();
    expect(screen.getByText("Remove the lid")).toBeInTheDocument();
  });

  it("renders exceptions when present", () => {
    render(
      <MaterialDetail
        page={makePage({
          rule: {
            disposition: "curbside_recycle",
            acceptedStatus: "conditional",
            preparationSteps: [],
            exceptions: ["Not aerosol cans"],
            warnings: [],
          },
        })}
      />,
    );
    expect(screen.getByText("Exceptions")).toBeInTheDocument();
    expect(screen.getByText("Not aerosol cans")).toBeInTheDocument();
  });

  it("renders warnings when present", () => {
    render(
      <MaterialDetail
        page={makePage({
          rule: {
            disposition: "curbside_recycle",
            acceptedStatus: "accepted",
            preparationSteps: [],
            exceptions: [],
            warnings: ["Do not crush"],
          },
        })}
      />,
    );
    expect(screen.getByText("Warnings")).toBeInTheDocument();
    expect(screen.getByText("Do not crush")).toBeInTheDocument();
  });
});

describe("MaterialDetail -- citations", () => {
  it("renders a blockquote when citation has a quote", () => {
    render(<MaterialDetail page={makePage()} />);
    const blockquote = screen.getByRole("blockquote");
    expect(blockquote).toHaveTextContent(
      "Aluminum cans are accepted curbside.",
    );
  });

  it("renders no blockquote when citation quote is null", () => {
    render(
      <MaterialDetail
        page={makePage({
          citations: [{ ...citation, quote: null }],
        })}
      />,
    );
    expect(screen.queryByRole("blockquote")).not.toBeInTheDocument();
  });

  it("renders no Sources section when citations array is empty (INV-PROD-001 regression)", () => {
    render(<MaterialDetail page={makePage({ citations: [] })} />);
    expect(screen.queryByText("Sources")).not.toBeInTheDocument();
  });
});
