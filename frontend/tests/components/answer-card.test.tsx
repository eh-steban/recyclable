import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AnswerCard } from "@/components/answer-card";
import { makeAnswer } from "@/tests/fixtures/answers";
import { makeCitation, DENVER_RECYCLING_URL } from "@/tests/fixtures/citations";

describe("AnswerCard -- short-answer badge", () => {
  it("renders yes badge for yes short_answer", () => {
    render(<AnswerCard answer={makeAnswer({ shortAnswer: "yes" })} />);
    expect(screen.getByText("yes")).toBeInTheDocument();
  });

  it("renders no badge for no short_answer", () => {
    render(<AnswerCard answer={makeAnswer({ shortAnswer: "no" })} />);
    expect(screen.getByText("no")).toBeInTheDocument();
  });

  it("renders conditional badge", () => {
    render(<AnswerCard answer={makeAnswer({ shortAnswer: "conditional" })} />);
    expect(screen.getByText("conditional")).toBeInTheDocument();
  });

  it("renders unknown badge for refusal", () => {
    render(
      <AnswerCard
        answer={makeAnswer({
          shortAnswer: "unknown",
          refusalReason: "no_evidence",
          citations: [],
        })}
      />,
    );
    expect(screen.getByText("unknown")).toBeInTheDocument();
  });
});

describe("AnswerCard -- recommended action", () => {
  it("renders recommended_action text", () => {
    render(
      <AnswerCard
        answer={makeAnswer({
          recommendedAction: "Place in your blue recycling cart.",
        })}
      />,
    );
    expect(
      screen.getByText("Place in your blue recycling cart."),
    ).toBeInTheDocument();
  });
});

describe("AnswerCard -- preparation_steps hidden when empty", () => {
  it("renders no preparation steps section when array is empty", () => {
    render(<AnswerCard answer={makeAnswer({ preparationSteps: [] })} />);
    expect(screen.queryByText(/preparation steps/i)).not.toBeInTheDocument();
  });

  it("renders preparation steps when non-empty", () => {
    render(
      <AnswerCard
        answer={makeAnswer({
          preparationSteps: ["Rinse the can", "Remove the lid"],
        })}
      />,
    );
    expect(screen.getByText(/preparation steps/i)).toBeInTheDocument();
    expect(screen.getByText("Rinse the can")).toBeInTheDocument();
  });
});

describe("AnswerCard -- do_not_do hidden when empty", () => {
  it("renders no do-not-do section when array is empty", () => {
    render(<AnswerCard answer={makeAnswer({ doNotDo: [] })} />);
    expect(screen.queryByText(/do not/i)).not.toBeInTheDocument();
  });

  it("renders do_not_do items when non-empty", () => {
    render(
      <AnswerCard answer={makeAnswer({ doNotDo: ["Do not crush cans"] })} />,
    );
    // Section heading exists (use heading role for specificity)
    expect(
      screen.getByRole("heading", { name: /do not/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Do not crush cans")).toBeInTheDocument();
  });
});

describe("AnswerCard -- citations", () => {
  it("renders a citation link with title and url", () => {
    render(
      <AnswerCard
        answer={makeAnswer({
          citations: [
            makeCitation({
              title: "Denver Recycling Guide",
              url: DENVER_RECYCLING_URL,
            }),
          ],
        })}
      />,
    );
    const link = screen.getByRole("link", { name: "Denver Recycling Guide" });
    expect(link).toHaveAttribute("href", "https://www.denvergov.org/recycling");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("renders a blockquote when citation has a quote", () => {
    render(
      <AnswerCard
        answer={makeAnswer({
          citations: [
            makeCitation({ quote: "Aluminum cans are accepted curbside." }),
          ],
        })}
      />,
    );
    const blockquote = screen.getByRole("blockquote");
    expect(blockquote).toHaveTextContent(
      "Aluminum cans are accepted curbside.",
    );
  });

  it("renders no blockquote when citation has no quote", () => {
    render(
      <AnswerCard
        answer={makeAnswer({
          citations: [{ title: "No quote", url: "https://example.com" }],
        })}
      />,
    );
    expect(screen.queryByRole("blockquote")).not.toBeInTheDocument();
  });
});

describe("AnswerCard -- confidence badge", () => {
  it("renders high confidence badge", () => {
    render(<AnswerCard answer={makeAnswer({ confidence: "high" })} />);
    expect(screen.getByText("high")).toBeInTheDocument();
  });

  it("renders medium confidence badge", () => {
    render(<AnswerCard answer={makeAnswer({ confidence: "medium" })} />);
    expect(screen.getByText("medium")).toBeInTheDocument();
  });

  it("renders low confidence badge", () => {
    render(<AnswerCard answer={makeAnswer({ confidence: "low" })} />);
    expect(screen.getByText("low")).toBeInTheDocument();
  });
});

describe("AnswerCard -- clarifying_question", () => {
  it("renders the clarifying question when non-null", () => {
    render(
      <AnswerCard
        answer={makeAnswer({
          shortAnswer: "unknown",
          clarifyingQuestion: "Did you mean cardboard or plastic?",
          citations: [],
          preparationSteps: [],
          doNotDo: [],
        })}
      />,
    );
    expect(
      screen.getByText("Did you mean cardboard or plastic?"),
    ).toBeInTheDocument();
  });

  it("does not render recommended_action when clarifying question is present", () => {
    render(
      <AnswerCard
        answer={makeAnswer({
          shortAnswer: "unknown",
          clarifyingQuestion: "Did you mean cardboard or plastic?",
          recommendedAction: "Should not appear",
        })}
      />,
    );
    expect(screen.queryByText("Should not appear")).not.toBeInTheDocument();
  });
});

describe("AnswerCard -- OOJ refusal (Aurora)", () => {
  const oojAnswer = makeAnswer({
    shortAnswer: "unknown",
    refusalReason: "out_of_jurisdiction",
    citations: [],
    jurisdiction: { id: null, name: "Aurora" },
    recommendedAction: "",
  });

  it("renders unknown badge for OOJ refusal", () => {
    render(<AnswerCard answer={oojAnswer} />);
    expect(screen.getByText("unknown")).toBeInTheDocument();
  });

  it("names the location (Aurora) in the refusal text", () => {
    render(<AnswerCard answer={oojAnswer} />);
    expect(screen.getByText(/Aurora/)).toBeInTheDocument();
  });

  it("renders NO citation link for OOJ refusal (INV-PROD-001)", () => {
    render(<AnswerCard answer={oojAnswer} />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});

describe("AnswerCard -- no_evidence refusal", () => {
  const noEvidenceAnswer = makeAnswer({
    shortAnswer: "unknown",
    refusalReason: "no_evidence",
    clarifyingQuestion: null,
    citations: [],
    recommendedAction: "",
  });

  it("renders fallback refusal text (INV-PROD-001)", () => {
    render(<AnswerCard answer={noEvidenceAnswer} />);
    expect(
      screen.getByText(
        /no verified recycling rule was found for this question/i,
      ),
    ).toBeInTheDocument();
  });

  it("renders NO citation link for no_evidence refusal (INV-PROD-001)", () => {
    render(<AnswerCard answer={noEvidenceAnswer} />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
