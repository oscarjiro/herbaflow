/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { TanStackRouterVite } from "@tanstack/router-plugin/vite";
import { defineConfig } from "vite";
import path from "node:path";

export default defineConfig({
  plugins: [
    TanStackRouterVite({ target: "react", autoCodeSplitting: true }),
    react(),
    tailwindcss(),
  ],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    // The setup-form integration tests drive a debounced search combobox across
    // several steps; under full-suite parallel load the default 5s test budget is
    // too tight and they intermittently time out (they pass fast in isolation).
    testTimeout: 20000,
    hookTimeout: 20000,
    // Resilience to environment jitter: heavy jsdom integration tests can flake
    // under parallel load (timers starved). A real failure still fails every attempt.
    retry: 2,
  },
});
