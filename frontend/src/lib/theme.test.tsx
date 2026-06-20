import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ThemeProvider, useTheme } from "./theme";

function Probe() {
  const { pref, resolved, setPref } = useTheme();
  return (
    <div>
      <span data-testid="pref">{pref}</span>
      <span data-testid="resolved">{resolved}</span>
      <button onClick={() => setPref("light")}>light</button>
      <button onClick={() => setPref("dark")}>dark</button>
      <button onClick={() => setPref("system")}>system</button>
    </div>
  );
}

const setSystemDark = (v: boolean) =>
  (globalThis as unknown as { __setMatchMediaDark: (v: boolean) => void }).__setMatchMediaDark(v);

beforeEach(() => {
  localStorage.clear();
  setSystemDark(false);
  document.documentElement.classList.remove("dark");
});
afterEach(() => localStorage.clear());

describe("ThemeProvider tri-state", () => {
  it("defaults to system and resolves via prefers-color-scheme", () => {
    setSystemDark(true);
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId("pref").textContent).toBe("system");
    expect(screen.getByTestId("resolved").textContent).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("tracks live OS changes while pref is system", () => {
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId("resolved").textContent).toBe("light");
    act(() => setSystemDark(true));
    expect(screen.getByTestId("resolved").textContent).toBe("dark");
  });

  it("explicit light/dark overrides the OS and persists", () => {
    setSystemDark(true);
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    act(() => screen.getByText("light").click());
    expect(screen.getByTestId("resolved").textContent).toBe("light");
    expect(localStorage.getItem("hf-theme")).toBe("light");
    // a later OS change must NOT move an explicit choice
    act(() => setSystemDark(false));
    expect(screen.getByTestId("resolved").textContent).toBe("light");
  });
});
