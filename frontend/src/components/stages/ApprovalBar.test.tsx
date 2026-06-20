import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApprovalBar } from "./ApprovalBar";

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
        disabledReason="No disease targets found. Lower the minimum score, run this step again, or add one to continue."
        onApprove={onApprove}
      />,
    );
    expect(screen.getByRole("button", { name: /approve/i })).toBeDisabled();
    expect(screen.getByText(/run this step again/i)).toBeInTheDocument();
  });

  it("disables the button while pending without showing a disabledReason", () => {
    render(
      <ApprovalBar
        stage={4}
        status="stage_4_awaiting_approval"
        currentStage={4}
        pending
        disabledReason="Should not appear"
        onApprove={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: /approve/i })).toBeDisabled();
    expect(screen.queryByText("Should not appear")).not.toBeInTheDocument();
  });

  it("shows disabledReason only when disabled is true, not when only pending", () => {
    const { rerender } = render(
      <ApprovalBar
        stage={4}
        status="stage_4_awaiting_approval"
        currentStage={4}
        disabled={false}
        pending
        disabledReason="Blocking reason"
        onApprove={() => {}}
      />,
    );
    // pending alone: button disabled but no reason text
    expect(screen.getByRole("button", { name: /approve/i })).toBeDisabled();
    expect(screen.queryByText("Blocking reason")).not.toBeInTheDocument();

    // disabled alone: button disabled AND reason shown
    rerender(
      <ApprovalBar
        stage={4}
        status="stage_4_awaiting_approval"
        currentStage={4}
        disabled
        pending={false}
        disabledReason="Blocking reason"
        onApprove={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: /approve/i })).toBeDisabled();
    expect(screen.getByText("Blocking reason")).toBeInTheDocument();
  });
});
