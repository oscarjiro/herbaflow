# Herbaflow — agent instructions

This project keeps its instructions in `CLAUDE.md` files so there is one canonical copy per scope.

- **Start here:** [`CLAUDE.md`](./CLAUDE.md) — stack, source-of-truth precedence, conventions, gates.
- **Working in the backend:** [`backend/CLAUDE.md`](./backend/CLAUDE.md) — layering and the canonical
  home for every concern (identity, resolution, each pipeline stage, export, security, errors).
- **Working in the frontend:** [`frontend/CLAUDE.md`](./frontend/CLAUDE.md) — directory map,
  generated-code rules, design tokens, test layout.
- **Working in the ETL:** [`etl/CLAUDE.md`](./etl/CLAUDE.md) and the per-pipeline files under
  `etl/compounds/`, `etl/diseases/`, and `etl/disease_targets/`.

Read the file for the scope you are editing before changing code in it.
