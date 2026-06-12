import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useAddWithDedup } from "./useAddWithDedup";

type Item = { id: string; name: string };

describe("useAddWithDedup", () => {
  it("splits resolved into already-in-run vs new and emits only new ids", () => {
    const onAddIds = vi.fn();
    const current = new Set(["a"]);
    const { result } = renderHook(() =>
      useAddWithDedup<Item>({ currentIds: current, getId: (i) => i.id, onAddIds }),
    );
    act(() => {
      result.current.handleAdd([
        { id: "a", name: "Alpha" },
        { id: "b", name: "Beta" },
      ]);
    });
    expect(onAddIds).toHaveBeenCalledWith(["b"]);
    expect(result.current.alreadyInRun.map((i) => i.id)).toEqual(["a"]);
  });

  it("does not call onAddIds when everything is already present", () => {
    const onAddIds = vi.fn();
    const { result } = renderHook(() =>
      useAddWithDedup<Item>({ currentIds: new Set(["a"]), getId: (i) => i.id, onAddIds }),
    );
    act(() => result.current.handleAdd([{ id: "a", name: "Alpha" }]));
    expect(onAddIds).not.toHaveBeenCalled();
    expect(result.current.alreadyInRun).toHaveLength(1);
  });
});
