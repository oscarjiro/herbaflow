import { beforeEach, expect, test, vi } from "vitest";
import { toast } from "sonner";
import { notifyError, notifySuccess } from "./toast";

vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), info: vi.fn() } }));
beforeEach(() => vi.clearAllMocks());

test("notifyError humanizes a problem body", () => {
  notifyError({ detail: "Service temporarily unavailable." });
  expect(toast.error).toHaveBeenCalledWith("Service temporarily unavailable.");
});

test("notifySuccess passes the message through", () => {
  notifySuccess("Added 3 compounds");
  expect(toast.success).toHaveBeenCalledWith("Added 3 compounds");
});
