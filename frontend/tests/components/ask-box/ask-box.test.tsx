import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AskBox } from "@/components/ask-box/ask-box";
import { makeOkAnswer } from "@/tests/fixtures/answers";

// Mock the Server Action so tests don't hit the network.
vi.mock("@/app/ask/actions", () => ({
  submitAsk: vi.fn(),
}));

import { submitAsk } from "@/app/ask/actions";
const mockSubmitAsk = vi.mocked(submitAsk);

describe("AskBox -- form renders", () => {
  it("renders location input with placeholder", () => {
    render(<AskBox />);
    expect(
      screen.getByPlaceholderText("City (Denver supported)"),
    ).toBeInTheDocument();
  });

  it("renders question textarea with placeholder", () => {
    render(<AskBox />);
    expect(
      screen.getByPlaceholderText("e.g. Can I recycle cardboard in Denver?"),
    ).toBeInTheDocument();
  });

  it("renders a submit button", () => {
    render(<AskBox />);
    expect(screen.getByRole("button", { name: /ask/i })).toBeInTheDocument();
  });
});

describe("AskBox -- happy path renders answer card", () => {
  beforeEach(() => {
    mockSubmitAsk.mockResolvedValue(
      makeOkAnswer({ recommendedAction: "Place in your blue recycling cart." }),
    );
  });

  it("renders AnswerCard with recommended_action after submit", async () => {
    // delay: null eliminates inter-keystroke delays that cause
    // timeouts under full-suite vitest worker contention.
    const user = userEvent.setup({ delay: null });
    render(<AskBox />);

    await user.type(
      screen.getByPlaceholderText("City (Denver supported)"),
      "Denver",
    );
    await user.type(
      screen.getByPlaceholderText("e.g. Can I recycle cardboard in Denver?"),
      "Can I recycle aluminum cans?",
    );
    await user.click(screen.getByRole("button", { name: /ask/i }));

    await waitFor(() => {
      expect(
        screen.getByText("Place in your blue recycling cart."),
      ).toBeInTheDocument();
    });
  });

  it("disables button and shows Checking... while in-flight", async () => {
    const okAnswer = makeOkAnswer({
      recommendedAction: "Place in your blue recycling cart.",
    });
    let resolve: (v: typeof okAnswer) => void;
    const deferred = new Promise<typeof okAnswer>((res) => (resolve = res));
    mockSubmitAsk.mockReturnValueOnce(deferred);

    const user = userEvent.setup({ delay: null });
    render(<AskBox />);

    await user.type(
      screen.getByPlaceholderText("City (Denver supported)"),
      "Denver",
    );
    await user.type(
      screen.getByPlaceholderText("e.g. Can I recycle cardboard in Denver?"),
      "Can I recycle aluminum cans?",
    );
    await user.click(screen.getByRole("button", { name: /ask/i }));

    const btn = screen.getByRole("button", { name: /checking/i });
    expect(btn).toBeDisabled();

    resolve!(okAnswer);
    await waitFor(() => {
      expect(
        screen.getByText("Place in your blue recycling cart."),
      ).toBeInTheDocument();
    });
  });
});

describe("AskBox -- error state", () => {
  beforeEach(() => {
    mockSubmitAsk.mockResolvedValue({
      ok: false,
      error: "internal_error",
    });
  });

  it("renders error message when action returns ok:false", async () => {
    const user = userEvent.setup({ delay: null });
    render(<AskBox />);

    await user.type(
      screen.getByPlaceholderText("City (Denver supported)"),
      "Denver",
    );
    await user.type(
      screen.getByPlaceholderText("e.g. Can I recycle cardboard in Denver?"),
      "Can I recycle aluminum cans?",
    );
    await user.click(screen.getByRole("button", { name: /ask/i }));

    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
    });

    expect(screen.queryByRole("article")).not.toBeInTheDocument();
  });
});
