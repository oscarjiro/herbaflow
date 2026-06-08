import { defineConfig } from "@hey-api/openapi-ts";

// OpenAPI -> TypeScript codegen: types + fetch client + Zod response schemas +
// TanStack Query option helpers, all generated from backend/openapi.json.
export default defineConfig({
  input: "../backend/openapi.json",
  output: { path: "src/api", format: "prettier" },
  plugins: [
    "@hey-api/client-fetch",
    "zod",
    // Query option helpers only; mutations call the generated SDK functions
    // directly (the plugin's mutation helpers don't type-narrow under the
    // pinned client-fetch version).
    { name: "@tanstack/react-query", mutationOptions: false },
  ],
});
