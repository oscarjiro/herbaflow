import { act, fireEvent, render, screen } from "@testing-library/react";
import { LazyMotion, domAnimation } from "motion/react";
import { describe, expect, it, vi } from "vitest";
import { ApprovalBar } from "./ApprovalBar";

/** Wrap with LazyMotion so m.* components in StatefulButton work. */
function Wrapper({ children }: { children: React.ReactNode }) {
  return <LazyMotion features={domAnimation}>{children}</LazyMotion>;
}

describe("ApprovalBar", () => {
  it("renders only for the matching stage at an awaiting checkpoint", () => {
    const { rerender } = render(
      <ApprovalBar
        stage={4}
        status="stage_4_awaiting_approval"
        currentStage={4}
        onApprove={() => Promise.resolve()}
      />,
      { wrapper: Wrapper },
    );
    expect(screen.getByRole("button", { name: /approve/i })).toBeInTheDocument();

    // A view whose stage is not the current stage renders nothing.
    rerender(
      <Wrapper>
        <ApprovalBar
          stage={2}
          status="stage_4_awaiting_approval"
          currentStage={4}
          onApprove={() => Promise.resolve()}
        />
      </Wrapper>,
    );
    expect(screen.queryByRole("button", { name: /approve/i })).not.toBeInTheDocument();
  });

  it("disables Approve and shows the reason when disabled", () => {
    const onApprove = vi.fn().mockResolvedValue(undefined);
    render(
      <ApprovalBar
        stage={4}
        status="stage_4_awaiting_approval"
        currentStage={4}
        disabled
        disabledReason="No disease targets found. Lower the minimum score, run this step again, or add one to continue."
        onApprove={onApprove}
      />,
      { wrapper: Wrapper },
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
        onApprove={() => Promise.resolve()}
      />,
      { wrapper: Wrapper },
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
        onApprove={() => Promise.resolve()}
      />,
      { wrapper: Wrapper },
    );
    // pending alone: button disabled but no reason text
    expect(screen.getByRole("button", { name: /approve/i })).toBeDisabled();
    expect(screen.queryByText("Blocking reason")).not.toBeInTheDocument();

    // disabled alone: button disabled AND reason shown
    rerender(
      <Wrapper>
        <ApprovalBar
          stage={4}
          status="stage_4_awaiting_approval"
          currentStage={4}
          disabled
          pending={false}
          disabledReason="Blocking reason"
          onApprove={() => Promise.resolve()}
        />
      </Wrapper>,
    );
    expect(screen.getByRole("button", { name: /approve/i })).toBeDisabled();
    expect(screen.getByText("Blocking reason")).toBeInTheDocument();
  });

  it("enters the loading state on click and calls onApprove", async () => {
    // Never resolves so we can assert the loading state while in-flight.
    let resolveFn!: () => void;
    const onApprove = vi.fn(
      () =>
        new Promise<void>((res) => {
          resolveFn = res;
        }),
    );
    render(
      <ApprovalBar
        stage={4}
        status="stage_4_awaiting_approval"
        currentStage={4}
        onApprove={onApprove}
      />,
      { wrapper: Wrapper },
    );

    const btn = screen.getByRole("button", { name: /approve/i });

    // fireEvent.click is synchronous; handleClick sets state to "loading"
    // before the await, so a synchronous act flush captures the loading state.
    act(() => {
      fireEvent.click(btn);
    });

    expect(onApprove).toHaveBeenCalledOnce();
    expect(screen.getByRole("button")).toHaveAttribute("aria-busy", "true");
    expect(screen.getByText("Working…")).toBeInTheDocument();

    // Resolve to clean up the hanging promise.
    await act(async () => {
      resolveFn();
    });
  });

  it("transitions to the success state after onApprove resolves", async () => {
    const onApprove = vi.fn(() => Promise.resolve());
    render(
      <ApprovalBar
        stage={4}
        status="stage_4_awaiting_approval"
        currentStage={4}
        onApprove={onApprove}
      />,
      { wrapper: Wrapper },
    );

    // Click and let the promise + state updates settle.
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /approve/i }));
    });

    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(onApprove).toHaveBeenCalledOnce();
  });
});
