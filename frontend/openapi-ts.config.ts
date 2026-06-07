import { defineConfig } from "@hey-api/openapi-ts";

// OpenAPI -> TypeScript codegen: generates types and a typed fetch client from
// the backend's committed OpenAPI snapshot (backend/openapi.json). The Zod and
// TanStack Query plugins are intentionally not enabled yet.
export default defineConfig({
  input: "../backend/openapi.json",
  output: { path: "src/api", format: "prettier" },
  plugins: ["@hey-api/client-fetch"],
});
