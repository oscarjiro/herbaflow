import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "src/api/**", "src/routeTree.gen.ts"] }, // generated files are not linted
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    rules: {
      // Security: block the primary XSS vector — dangerouslySetInnerHTML (spec §8).
      "no-restricted-syntax": [
        "error",
        {
          selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
          message: "dangerouslySetInnerHTML is banned (XSS). Render escaped values only.",
        },
      ],
    },
  },
);
