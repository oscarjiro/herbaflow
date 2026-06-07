import { defineConfig } from "@hey-api/openapi-ts";

// OpenAPI -> TypeScript codegen. Phase 0 establishes the pipeline + CI drift gate
// with types and a typed fetch client, reading the backend's committed OpenAPI
// snapshot (backend/openapi.json). The Zod and TanStack Query plugins (decision #8)
// are wired in a later phase, once real endpoints and schemas exist.
export default defineConfig({
  input: "../backend/openapi.json",
  output: { path: "src/api", format: "prettier" },
  plugins: ["@hey-api/client-fetch"],
});
