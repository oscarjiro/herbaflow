import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApprovalBar } from "../src/components/stages/ApprovalBar";

describe("ApprovalBar", () => {
  it("renders only for the matching stage at an awaiting checkpoint", () => {
    const { rerender } = render(
      <ApprovalBar
        stage={4}
        status="stage_4_awaiting_approval"
        currentStage={4}
        onApprove={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: /approve/i })).toBeInTheDocument();

    // A view whose stage is not the current stage renders nothing.
    rerender(
      <ApprovalBar
        stage={2}
        status="stage_4_awaiting_approval"
        currentStage={4}
        onApprove={() => {}}
      />,
    );
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
  });

  it("disables Approve and shows the reason when disabled", () => {
    const onApprove = vi.fn();
    render(
      <ApprovalBar
        stage={4}
        status="stage_4_awaiting_approval"
        currentStage={4}
        disabled
        disabledReason="No disease targets — lower min score or add one to continue."
        onApprove={onApprove}
      />,
    );
    expect(screen.getByRole("button", { name: /approve/i })).toBeDisabled();
    expect(screen.getByText(/lower min score/i)).toBeInTheDocument();
  });
});
