# Backend (`/backend`)

FastAPI + SQLAlchemy 2.0 async + Pydantic v2, run with **uv**. Layered: Routers (HTTP only) → Services/engine
→ Repository → DB. Stage code never inlines SQL.

> The application is complete; the map below is what the package contains today:
> `app/main.py` (`/health`), `app/config.py`, `app/clock.py`, `app/db.py` (async engine +
> `get_session` + `session_scope`), `app/errors.py` (RFC 9457 problem+json),
> `app/contracts.py` (contract loader + `default_mode` + ADME/target bounds/defaults + entity-cap accessors),
> `app/models/` (disease, plant, compound, plant_compound, target, compound_target, disease_target,
> analysis_run, analysis_run_progress — all datetimes tz-aware), `app/schemas/` (disease, plant, analysis, compound,
> target, graph (`CtpGraph`) Pydantic DTOs), `app/repositories/` (disease, plant, analysis, compound, target,
> compound_target, disease_target — including `get_many`, `update_descriptors`, compound-edge reuse
> (`edges_for_compound`/`replace_for_compound`), `targets_for_disease`/`count_for_disease`),
> `app/services/` (disease, plant, analysis + canonical.py UUID v5 identity twin + structure.py RDKit
> identity + input_validation.py compound+target resolution + descriptors.py RDKit ADME descriptors/PAINS
> threadpool + gene_symbols.py offline HGNC normalizer),
> `app/integrations/` (`base.py` `with_retry` + `pubchem.py` + `uniprot.py` + `chembl.py` (load-bearing;
> raises 503 on outage) + `pubchem_bioassay.py` (supplementary; degrades to `[]` on outage) +
> `string_db.py` (STRING PPI network; load-bearing — 503 on outage, 404 = honest-empty network) +
> `gprofiler.py` (g:Profiler enrichment; **degrade-not-fail** — `GprofilerError` degrades to empty terms,
> contrast STRING's load-bearing 503)),
> `app/pipeline/` (`state.py`, `engine.py` stage-registry/DAG/multi-stage-dispatch/`reset_from`/
>  `mark_downstream_stale`/stale-aware `advance_run`,
> `edits.py` durable entity-keyed edit layer, `limits.py` entity caps, `stages/stage1.py`,
> `stages/stage2.py` ADME gate, `stages/stage3.py` compound→target ChEMBL∪PubChem BioAssay,
> `stages/stage4.py` disease→target filtered DB read of seeded `disease_targets`,
> `stages/stage5.py` overlap (pure S3∩S4 set intersection on `target_id`; no params, no statistics),
> `stages/stage6.py` STRING PPI network (`ppi` params; no protein-count cap, never blocked),
> `stages/stage7.py` hub-gene ranking (MCC ranking via networkx + four classic centralities reported; `hub_genes` param;
>   reads `stage_results["6"]`; pure, no DB/API),
> `stages/stage8.py` functional enrichment (`enrichment` params; query = Stage-5 overlap, background =
>   Stage-3 universe; min_term_size filter; honest-null/degrade; **terminal** — completion marks the run `complete`)),
> and the routers that wire `GET /diseases`, `GET /plants`,
> `POST /analyses` (202 + BackgroundTask), `GET /analyses/{id}`,
> `DELETE /analyses/{id}` (exit/hard-delete a run; the engine halts it mid-pipeline), `POST /analyses/{id}/advance`,
> `POST /analyses/{id}/reset-from/{stage}`, `POST /analyses/{id}/stages/{stage}/edit`,
> `POST /compounds/validate`, `POST /targets/validate`,
> the results-handoff export (complete-only → 409): 4 bundles
> (`/export/report.md`, `/export/network-and-docking.zip`, `/export/stages.zip`,
> `/export/all-results.zip`) + per-artifact CSV endpoints + ONE generalized `/export/{filename}`
> (serves any per-stage CSV / chart PNG, 404s an unknown or undrawable artifact). Integration tests run against real Postgres via testcontainers.
> The sections below list the canonical home for each concern. Reuse them; never add a second variant.

## One canonical home per concern
- Identity (UUID v5): `app/services/canonical.py`
- Manual-input resolution (compounds + targets): `app/services/input_validation.py`
  — `resolve_compounds` for Step 1: deduplicates by raw token first (one `identity_from_smiles` call per
    distinct SMILES, via `asyncio.to_thread` gathered in parallel), then by `canonical_key` (two SMILES mapping
    to the same InChIKey collapse to one work item; InChIKey inputs share the same key-space). InChIKey
    detection is case-insensitive (`structure.is_inchikey` upper-cases before matching) so a lowercase
    InChIKey is recognized as a key rather than misrouted to the SMILES parser. DB lookups and
    upserts stay serial on the single session; PubChem enrichment for DB misses fans out via `asyncio.gather`.
    Invalid tokens fail per original line. `manual_source_id()` is called only on the structure-only path (one
    call site). Successful `ResolvedCompound` rows carry `pubchem_cid` when the canonical compound has one;
    failures carry a 1-based `line` index (parity with `resolve_targets`; Software Lock 4.5 per-line reason)
    so callers can map each `FailedInput` back to its input line.
  — `resolve_targets` for Step 3 (gene symbol OR UniProt accession to human 9606 canonical target): same phased
    shape as `resolve_compounds` — dedup by normalized identity in Phase 0, serial DB-first in Phases 1/2,
    parallel network (UniProt) fan-out via `asyncio.gather` in Phase 2, serial persist in Phase 3, emit in
    Phase 4. DB stays serial on the single session throughout. For a gene symbol, Phase 1 is DB-first
    (`TargetRepository.get_by_gene_symbol`, single-match only) before the UniProt `resolve_symbol` round-trip.
    Failures carry a precise `FailedInput.reason`: an InChIKey-shaped input reports "looks like a compound
    InChIKey, not a gene symbol or UniProt accession"; an unrecognized identifier reports "not a recognized
    human (9606) gene symbol or UniProt accession" (never an organism-blame message); a recognized HGNC gene
    with no UniProt protein (a non-coding RNA gene) reports "a recognized human gene with no protein in
    UniProt (likely a non-coding RNA gene, which has no protein target)" via `_symbol_fail_reason` (the one
    home, keyed off `gene_symbols.normalize(...).status`). (Extends G-5 honest-error.)
    Two classification edge cases are handled in Phase 0/3.5: (a) a TYPELESS token shaped like a UniProt
    accession but absent from UniProt is retried as a gene symbol (`from_grammar` flag → Phase 3.5 symbol
    fallback) because some real gene symbols collide with the accession grammar (e.g. P2RY12 == Q9H244; a
    strict regex cannot separate them from `P12345`); an EXPLICIT `type=uniprot` is never retried. (b) a
    UniProt isoform id (`P00533-2`) resolves via its base accession (`_accession_base` strips the `-<n>`
    suffix; there is no separate UniProt entry for an isoform).
  — `resolve_target_accession` is the **single** accession→canonical-target resolver: it canonicalizes
    identity on the UniProt **primary** accession (via `UniProtClient.resolve`, which searches
    `accession:` ∪ `sec_acc:`), so every alias/secondary accession of one protein converges to one
    `target_id`. Returns `AccessionResolution(target, reason)` (the `reason` is a `UniProtReason`); used by
    **both** `resolve_targets` (manual/STP) and `stage3.run` (which reads `.target`) — never duplicate it.
- Display-label resolution (id→name, single home): `app/services/labels.py` `resolve_entity_labels`
  — turns a run's `plant_ids`/`disease_id` into display name(s) from the catalog (multiple plants join
  on ", " in catalog order; missing ids → None). Shared by `analysis.create` (stores the resolved names
  on `parameters.labels` at create so the frontend never re-fetches the catalog to name the subject) and
  `services/export._resolve_labels` (falls back to it for legacy runs with no stored labels). Display-only
  (B4); never identity.
- HGNC normalization (offline gzip map, identity fallback): `app/services/gene_symbols.py`
- Distinct-gene-symbol extraction (one home): `app/pipeline/genes.py` — `distinct_gene_symbol_rows` (rows, for Stage 6) + `distinct_gene_symbols` (list[str], for Stage 8); both = "distinct non-null gene_symbol, first-seen order" (B-DUP-3, replaces the old stage6 `_mappable` / stage8 `_gene_symbols`).
- RDKit descriptor fallback (manual compounds, ADME-on, threadpool): `app/services/descriptors.py`
- Compound edit identity (one home): `AnalysisService._compound_add_entry` carries `compound_id`,
  `canonical_name`, `inchikey`, `smiles`, `pubchem_cid`, and `source_url` into Stage-1 manual prefills and
  edit-add rows; do not rebuild this shape at call sites. `AnalysisService.get` read-hydrates legacy
  Stage-1 rows that predate this carry only when those identity fields are missing, using the same
  `_compound_add_entry` shape from the canonical compound row.
- Pure-compute deps: `networkx` (Stage 7 — `networkx.Graph` + MCC via maximal-clique enumeration
  (`find_cliques`, Bron–Kerbosch) for the rank, plus degree/betweenness/closeness/eigenvector centrality
  reported per protein, all in-memory, no I/O).
- External clients (one per API) + the single `with_retry`: `app/integrations/`
  — `pubchem.py` (compound structure/identity), `uniprot.py` (accession + gene-symbol resolution, organism 9606;
    `resolve`/`resolve_symbol` return `UniProtResolution(record, reason)` — `UniProtReason.INVALID_ID` on a 400,
    `NO_HUMAN_RECORD` on a valid empty query — so callers can report the real cause),
    `chembl.py` (measured bioactivities; **load-bearing** — 503 on outage),
    `pubchem_bioassay.py` (active assay outcomes; **supplementary** — degrades to `[]` on outage),
    `string_db.py` (STRING PPI network, POST `/api/json/network`, species 9606, ~1 req/s; **load-bearing** — 503 on outage, 404 = honest-empty network; also `fetch_network_image` → STRING's server-rendered PNG POST `/api/image/network` (standard resolution, not high-res, to keep the persisted base64 small), **supplementary/degrade-to-None** never raises, sharing the one throttle + body builder `_throttled_post`/`_network_body` with `network()`)
- Target ORM model: `app/models/target.py`; CompoundTarget edge model: `app/models/compound_target.py`
- Target repository (upsert; `get_by_key`; `get_by_gene_symbol` = DB-first symbol→accession cache, single-match only so ambiguity falls back to UniProt): `app/repositories/target.py`; CompoundTarget repository (measured edges only; chembl_bioactivity > pubchem_bioassay precedence is decided in Stage 3 before write; `edges_for_compound` (joined read carrying the discovery params) + `replace_for_compound` (delete-then-insert a compound's edge set) back the Stage-3 D9 reuse): `app/repositories/compound_target.py`
- Stage 3 (compound→target identification, ChEMBL ∪ PubChem BioAssay, dedupe, coverage): `app/pipeline/stages/stage3.py`. D9: reuses a compound's persisted edges instead of re-calling externals when the run's discovery params are compatible (min_assay_confidence exact-match AND min_pchembl equal-or-looser, re-filtering pchembl; PubChem edges always kept; null params → refetch); replaces (not accretes) a compound's edges on fetch, stamping `min_pchembl`/`min_assay_confidence`.
- DiseaseTarget edge model: `app/models/disease_target.py`; DiseaseTarget repository (`targets_for_disease`
  score-filtered read joined to `targets` + `count_for_disease`): `app/repositories/disease_target.py`
- Stage 4 (disease→target collection): `app/pipeline/stages/stage4.py` — a **filtered DB read** of the
  ETL-seeded `disease_targets` (`opentargets_score >= min_score`, joined to `targets`, ordered by opentargets_score desc), keyed on
  the run's `disease_id`; human-only (9606), fixed. Open Targets is an ETL-time source, **not** a live call.
  Emits **one enriched `targets` list** (each row carries gene_symbol/uniprot_accession/opentargets_score/association_type/
  source_url) — no separate `disease_targets` view list; the edit layer preserves these fields so the opentargets_score
  survives an edit and reaches S5/S6 (B-DUP-2/L-11). An empty result parks at the checkpoint with a count-0
  honesty note; guided refuses Approve & Continue until the user lowers `min_score` or adds a target (auto
  hard-fails). An edit can never empty a stage.
- Stage 5 (overlap): `app/pipeline/stages/stage5.py` — pure set intersection of the run's Stage-3 ∩ Stage-4
  edit-layer `targets` lists on `target_id` (reads S4's `targets`, **not** a `disease_targets` view; excludes
  `user-removed` rows on BOTH sides so the overlap is the effective set + stays S3/S4-symmetric; carries S4's
  `opentargets_score` into the overlap). The field-standard raw overlap (à la Venny/jvenn) — **no parameters,
  no statistics, no external API** (OV-1); keeps the two descriptive side-counts (`compound_target_count`/
  `disease_target_count`). 0-overlap is a terminal hard-stop in BOTH modes (OV-4, engine-driven).
- Stage 6 (PPI network): `app/pipeline/stages/stage6.py` — STRING network over the overlap's mappable
  gene symbols (`ppi` param group: `min_confidence`/`network_type`). There is NO protein-count cap:
  STRING imposes no maximum identifier count when the species is set, and the stage always sends
  9606, so it builds on ALL distinct mappable overlap gene symbols and never emits a blocked result.
  Constructs its own `httpx.AsyncClient` (mirrors `stage3.run`), injectable for tests. After building
  the result it also calls `StringClient.fetch_network_image` (same client, shared throttle) and
  persists the PNG base64 at `stage_results["6"]["network_image"]` (key OMITTED on failure; the image
  step can never fail the stage).
- g:Profiler enrichment client: `app/integrations/gprofiler.py` — POST `/api/gost/profile/`, custom
  background (`domain_scope:"custom"` + `background:[...]`), correction enum `g_SCS|fdr|bonferroni`
  (note `g_SCS` spelling — verbatim API value); per-term intersection genes recovered by zipping the
  submitted `query` against each result row's `intersections` evidence list (non-empty entry = that
  query gene is annotated to the term; live-confirmed 2026-06-12). **Degrade-not-fail:**
  `GprofilerError` degrades to empty terms (the run still completes); contrast STRING's load-bearing 503.
- Stage 7 (hub-gene ranking): `app/pipeline/stages/stage7.py` — pure networkx computation over the
  Stage-6 PPI graph (`hub_genes` param: `top_n`); reads `stage_results["6"]` edges; no DB or API calls.
  Ranks by **MCC** (Maximal Clique Centrality, Chin 2014 — the cytoHubba method): MCC(v) = sum over
  maximal cliques C ∋ v of (|C|−1)!, on the undirected/unweighted graph (Bron–Kerbosch enumeration; no
  edge among v's neighbours → MCC == degree; isolated node → 0). The four classic centralities
  (degree/betweenness/closeness/eigenvector, undirected) are still computed and **reported** per protein,
  not aggregated into the rank. `ranking_metric` is the constant `"mcc"`. Human-only (9606) inherited
  from S6 inputs — no new enforcement point. Tiny/sparse networks flagged and reported, never a hard-stop.
- Stage 8 (functional enrichment): `app/pipeline/stages/stage8.py` — enrichment of Stage-5 overlap
  gene symbols against the Stage-3 compound-target universe (custom background, method constant not
  config) via `GprofilerClient` (`enrichment` params: `significance_threshold`/`min_term_size`/`correction`/
  `sources`/`no_iea`). min_term_size filtered client-side. Honest-null: empty overlap → no g:Profiler call,
  `flags=["empty_input"]`. Degrade: `GprofilerError` → `degraded=True`, terms=[]. **Terminal stage**
  — completion sets `analysis_runs.completed_at` and transitions status to `complete`. A 0-term result
  is a valid completion; 0-overlap guard is in Stage 5, not here.
- Results-handoff export (capstone, complete-only): four layers, one concern.
  `app/pipeline/results_handoff.py` — **pure** builders (no DB/async/API) over a complete run's
  `stage_results` + pre-batched entity dicts; the **single graph-data home**: `build_ctp_graph`/
  `build_ppi_graph` (graph dicts) feed `build_ctp_nodes`/`build_ctp_edges`/`build_ppi_nodes`/
  `build_ppi_edges` (Cytoscape-importable CSVs — **de-UUID'd** node ids: compound = InChIKey [with a
  `smiles` column], target = gene symbol, pathway = term id; edge endpoints == node ids). Also
  `build_stage_csv` (per-stage S1–S8 CSV; empty stage → header + `# note`; the S8 enrichment CSV
  carries a derived per-term `source_url` via `_term_url` — GO→QuickGO, KEGG→kegg.jp, REAC→Reactome,
  WP→WikiPathways), `bundle_slug` (branded UUID-free download stem
  `herbaflow_{plant}_{disease}_{date}`), `build_report` (now a **thin delegate** to `app/pipeline/report.py`
  — the report model + renderer is the single home for the run's human-readable science), the **`.md`**
  READMEs (`build_network_readme`/`build_stages_readme`/`build_root_readme` — each with a per-column
  glossary; `build_all_results_bundle` **embeds** both sub-bundle READMEs at
  `network/README.md` + `stages/README.md`), and the bundles
  (`build_network_bundle`/`build_stages_bundle`/`build_all_results_bundle`; conditional-PNG → a None
  artifact is skipped). `build_stages_bundle`/`build_all_results_bundle` take `input_modes` and drop
  the per-stage CSVs of **not-applicable** stages (e.g. no `stage1_*`/`stage2_*` CSV in a
  manual-targets run) via `_drop_na_stage_files`, reusing `report.na_stages` + `report.STAGE_CSV_SLUG`.
  The per-stage CSV bundle slug map has ONE home: `report.STAGE_CSV_SLUG`; the NA-stage determination
  has ONE home: `report.na_stages` (public).
  `app/pipeline/report.py` — the **pure** report **model + markdown renderer** (no DB/async/API;
  imports only `contracts` + `entry_modes`): dataclasses `ReportModel`/`StageSection`/`ParamRow`/
  `SourceLink`/`PreviewTable`; `build_report_model(...)` assembles mode-aware interpretive **findings**
  (S1–S8 lead with scientific meaning, never `Result count:`), humanized params (`humanize_label`/
  `humanize_value`/`fmt_num` + units/descriptions from `contracts.pipeline_param_bounds`), `{name,url}`
  data-source links, and S7/S8 preview tables; `render_markdown(model)` emits the `.md` now (a PDF
  renderer can consume the same model later) — params render as a **markdown table**
  (`| Parameter | Value | Description |`), not bullets. **Not-applicable** stages (`na_stages(im)`,
  the public single home) get a one-liner finding only (params/sources/figure/csv/preview all empty).
  All display strings are free of em dashes and internal terminology. Provenance preserves the
  no-version-checksum honesty (Software Lock §6.4); footer omits the link when `frontend_url` is empty.
  `app/pipeline/charts.py` — the **pure** matplotlib renderer home (headless Agg → PNG bytes, or
  None when not drawable), publication conventions. ONE shared palette home: `SEQUENTIAL_CMAP`
  ("Reds"; high value = dark/saturated, never the invisible-yellow end) reused by the enrichment
  dotplot, the hub bar (`hub_bar_colors`), and the PPI node colouring; plus `ENRICHMENT_FULL_NAME`
  + `enrichment_title` (full category names) and `venn_title`. `render_venn(stage5, *, plant_label,
  disease_label)` (S5; titled with the actual plant + disease names, no "Stage 5"), `render_hub_bar`
  (S7; bars coloured by MCC via the shared palette), `render_enrichment_bubble` per category
  (S8; enrichplot dotplot — **x = −log10(adjusted p)**, **colour = gene count** on a continuous
  shared-palette colorbar, uniform bubbles, NO size legend, full-name title "Functional enrichment:
  …", "top 20 of M"; `ENRICHMENT_CATEGORIES` + `category_slug`), `render_ctp_network` (concentric
  shell layout, typed nodes + real labels, legend OUTSIDE the axes; above `CTP_FULL_RENDER_MAX` (~80)
  nodes draws the top high-degree **core** via `select_ctp_core`, balanced per type, "top N of M
  shown" — the full graph stays in the Cytoscape CSVs), `render_ppi_network` (the **matplotlib
  fallback**, used only when STRING's stored image is absent — kamada_kawai connected component,
  isolated nodes in a labelled tray, node colour = hub MCC on the shared palette, bounded to
  the top hub core via `select_ppi_core`/`PPI_FULL_RENDER_MAX`, full-term title "Protein-protein
  interaction network"). The old shared `render_network` is **retired**. New deps: matplotlib +
  matplotlib-venn.
  `app/services/export.py` `assemble_export` — the **only** DB touch: loads the run, **409 guard**
  (`ConflictProblem` unless `status == state.COMPLETE`) / 404 if missing, batch-fetches
  `CompoundRepository.get_many`/`TargetRepository.get_many`, resolves B4 labels (stored
  `parameters.labels` first, else plant names from `parameters.plant_ids` + `disease_id` via the
  catalog `list_all`), builds the artifact set incl. PNGs + the figure inventory; returns
  `ExportArtifacts` (with `network_bundle()`/`stages_bundle()`/`all_results_bundle()`). The PPI figure
  comes from `_ppi_figure` — the ONE decision point: prefer the **stored STRING image**
  (`sr["6"].network_image`, base64-decoded from the ORM row), fall back to `charts.render_ppi_network`
  on its absence or a decode error (so export makes **no** external call). The overlap Venn is given
  the resolved plant/disease labels; `input_modes` is threaded onto `ExportArtifacts` and into the
  stage/all-results bundles for the NA-stage CSV skip.
  `app/routers/export.py` — HTTP only: the 4 bundle endpoints (`/export/report.md`,
  `/export/network.zip`, `/export/stages.zip`, `/export/all-results.zip`) + per-artifact
  CSV endpoints + ONE generalized `/export/{filename}` (serves CSVs as `text/csv`, PNGs as
  `image/png`, 404s an undrawable/unknown artifact via an assembled-filename allowlist — guards
  path-injection, §8); lets the problems propagate to the global handler. **No migration, no new
  pipeline stage, no external call** — reads persisted `stage_results` only. Also serves the C-T-P
  graph as JSON (not a download, no `Content-Disposition`): `GET /analyses/{id}/ctp-graph` →
  `services/export.py` `assemble_ctp_graph` (typed `CtpGraph` from `app/schemas/graph.py`; same
  complete-only **409** / missing **404** guards; empty graph for compound-free runs) → reuses the
  single `results_handoff.build_ctp_graph` home + `_load_ctp_lookups` (the ONE entity-attribute
  batch-fetch, extracted from `assemble_export` so both the download artifacts and the JSON graph
  share one lookup build). The frontend renders this via its cytoscape `NetworkGraph` instead of
  re-deriving the graph client-side.
- Set-edit semantics (S1/S3/S4 add/remove): `app/services/analysis.py` `edit_stage` **stages** the change — it
  re-derives the *edited* stage in place, flags produced **downstream** stages `stale` (`engine.mark_downstream_stale`
  → `repositories/analysis.py` `mark_stages_stale`), records `parameters.rerun_from = min(edited stages)`, and
  re-runs **nothing** (the edit endpoint is synchronous — no BackgroundTask). `reset-from/{stage}` is the **sole**
  recompute; `advance` is refused **409** while any produced stage is `stale`. Honors the ledger D3 no-auto-recompute
  decision; mode-agnostic. The in-place re-derive rebuilds `computed_entities` from the **full** stored rows, so it
  preserves **every field the runner attached** (Stage-4 opentargets_score/association_type/source_url; Stage-3/4 gene_symbol/
  uniprot_accession) — a set edit never strips them, so the disease score still reaches S5/S6 and gene_symbol reaches
  S8 (B-DUP-2/L-11; a set-edit re-derive that dropped these was a silent bug caught by the live proof).
- STP paste-back: **run-scoped, no canonical DB edge** — the FE (`StpDialog`) parses the CSV, resolves the
  accessions via `POST /targets/validate`, and calls the Stage-3 edit path
  (`POST /analyses/{id}/stages/3/edit`) with the selected compound plus all resolved target IDs. Fresh targets
  are added to the run's Stage-3 target set, and the selected compound gets run-local
  `stage_results["3"].compound_targets` rows tagged `prediction_method="stp_import"`; coverage is recomputed
  from those in-run edges. There is no backend STP endpoint/service and no `compound_targets` table write.
- Manual disease-target add: **run-scoped, no `disease_targets` edge** — resolves via `POST /targets/validate`
  and applies via `POST /analyses/{id}/stages/4/edit`; persists the Target entity (canonical row) but never a
  disease→target relationship (Software Lock §6.2-E). Carries no association score.
- Input-mode stage-state matrix (entry-modes): `app/pipeline/entry_modes.py` — the **single** pure (no DB/IO)
  home mapping the 3 plant + 2 disease input modes → per-stage state (`computed`/`user_provided`/`not_applicable`),
  `frozen_stages` (engine skip-set), `first_computed_stage` (the create cursor), and `has_compounds`/
  `has_compounds_from_params` — the **compound-presence predicate** (`selection`/`manual_compounds` have
  compounds; `manual_targets` does not). C-T-P export outputs are gated by `results_handoff.ctp_is_emittable`
  (compounds AND a non-empty Stage-5 overlap AND a non-empty Stage-8 pathway set): `services/export.py`
  short-circuits `_network_files`/skips the CTP builders, `routers/export.py` 404s the `network.zip` bundle
  + per-artifact CTP routes via `_require_ctp`, and the FE mirrors it as `runHasCtp` (hides the network
  download). PPI stays (compound-independent). The frozen set is derived from
  `parameters.input_modes`, **never** from the presentational `stage_results[n].state` (which also reads
  `user_provided` for edited computed stages). Backward-compatible: a run with no `input_modes` → empty frozen set →
  engine behaves as a selection run.
- Create routing by input mode: `app/services/analysis.py` `create` — validates only each mode's lists, stamps the
  stage-state map + `current_stage`, pre-fills `user_provided` ENTITY stages THROUGH the edit layer (S1 compounds /
  S3 targets / S4 disease; S4 prefill seeds one enriched `targets` list — manual targets carry `source_url` but
  no score, no separate `disease_targets` view list; B-DUP-2/L-11), stamps `not_applicable` stages, stores
  `input_modes` + `labels` (manual free-text label per manual side; **selection sides resolve their
  catalog display name via `services/labels.resolve_entity_labels` and store it too**, so `labels` is the
  one display-name home for BOTH modes and the FE reads the subject straight off the run), and 422s a
  manual mode that resolves to 0 entities. Manual entities create
  NO catalog rows; manual disease → `disease_id` NULL. No migration (all jsonb). The shared `_target_add_entry`
  is the **single** target-identity builder — it carries gene_symbol/uniprot_accession **and** the UniProt
  `source_url` (derived from the accession), used by BOTH prefills AND `edit_stage`'s target-add path, so every
  target row (S3/S4, created or user-added) renders the UniProt link uniformly; callers never add `source_url`
  themselves (B2-sym). The FE Stage-3 view reads the accession off the row (falling back to the edge) so a
  user-provided/manual S3 — which has no `compound_targets` edges — still shows the linked accession (B2).
  The manual-compounds Stage-1 prefill (`_prefill_compound_stage`) is **async** and carries each compound's
  `canonical_name` into the edit-layer `added` entry — so Stage 1 displays the compound name rather than the
  UUID in `manual_compounds` mode (symmetric with the Stage-3 target prefill which already carried names).
- Engine frozen-stage skip: `app/pipeline/engine.py` `execute_run`/`advance_run`/`reset_from` skip the frozen set,
  never clear or recompute a frozen stage, and refuse a frozen stage as a **PARAM-Redo** `reset_from` target
  (`param_overrides is not None`). A **set-edit** reset (`param_overrides is None`) from a frozen stage IS allowed:
  `edit_stage` already re-derived that stage in place, so the reset reruns only its (non-frozen) downstream
  closure — the recovery path after editing a user-provided entity stage (manual compounds/targets/disease
  targets); without it a 0-overlap `failed` manual run was an un-editable dead-end. Composes with the F3 run-set.
  Array param overrides are validated element-wise against the contract `items.enum` (e.g. enrichment `sources` — REAC/WP accepted, unknown values 422) in `_validate_overrides`.
- Edit-layer field carry: `app/pipeline/edits.py` `normalize_edit`/`build_stage_entities` preserve **whatever
  fields the runner attaches** to each row (no fixed allowlist; `_CARRY_FIELDS` retired) — Stage 3/4 targets keep
  `gene_symbol`/`uniprot_accession`, and Stage 4 additionally keeps `opentargets_score`/`association_type`/`source_url`, so the
  disease association score survives a post-create Stage-4 edit and reaches S5/S6 (B-DUP-2/L-11). Compounds attach
  nothing extra, so a compound row stays minimal `{compound_id, canonical_name, tag}`.
- App-layer security (headers + payload cap + rate limiting): `app/security.py` — the one home for
  `SecurityHeadersMiddleware` (nosniff/Referrer-Policy/X-Frame-Options/`frame-ancestors 'none'` CSP),
  `PayloadSizeLimitMiddleware` (413 over `max_request_bytes`), and the slowapi `limiter` +
  `rate_limit_handler` (429 problem+json). Budgets in `app/config.py`; the 429/413 reuse `errors.py`
  `problem_json` (no second error shape). Narrative + OWASP walk-through: `docs/security.md`.
- Error mapping (RFC 9457): `app/errors.py` — incl. the DB-unavailable → **503** mapping
  (`_db_unavailable_handler`, registered for SQLAlchemy `OperationalError`/`InterfaceError`/`TimeoutError`).
- DB readiness probe: `app/db.py` `check_db` (`SELECT 1`); backs the DB-aware `GET /health` (200/503). Pool +
  asyncpg connect-timeout config (`pool_size`/`max_overflow`/`pool_timeout`/`pool_recycle`/connect `timeout`) lives
  in `init_engine` + `app/config.py` settings, so a dead database fails fast instead of hanging.
- Exit/delete a run: `DELETE /analyses/{id}` → `AnalysisService.delete` → `AnalysisRepository.delete`. The engine
  commits **per stage** and re-reads the run at each stage boundary, so a deleted run halts mid-pipeline
  (`execute_run`); `run_stages_task` rolls back + re-checks existence before recording a stage failure.
- Logging standard: `docs/observability.md` — the single `herbaflow.<area>` stdout stream.
- Startup reaper: `app/main.py` `_run_startup_reaper()` — called once in `lifespan` after
  `db.init_engine()` when `settings.async_database_url` is set; bulk-fails every stranded
  run (`pending` / `stage_N_running`) via `AnalysisRepository.fail_stranded`; errors are
  logged at WARNING and never block startup.  The stranded-status vocabulary has ONE home:
  `app/pipeline/state.py` `stranded_statuses()` (derived from `contracts.pipeline_stages()`
  + `stage_status()`; no hardcoded stage numbers).  `contracts.pipeline_stages()` is the one
  stage-set home — `engine.RUNNABLE_STAGES` consumes it too, so the engine's runnable set and the
  reaper's stranded set never drift.  Safe because the deployment is a single
  Render instance; multi-worker would need a heartbeat/`started_at` TTL instead.
- Security guide (posture, applied measures, OWASP Top 10:2025, validation matrix): `docs/security.md`.
- Contract loader: `app/contracts.py`
- ORM models (explicit `mapped_column(DateTime(timezone=True))`): `app/models/`
- Live per-item run progress: `app/pipeline/progress.py` `ProgressReporter` (throttled, best-effort,
  own session) writes the `analysis_run_progress` side table via `app/repositories/analysis_progress.py`;
  surfaced on `GET /analyses/{id}` as `AnalysisRead.progress` ONLY while `stage_2_running`/`stage_3_running`
  (status-gated in `AnalysisService.get`). Reported by Stage 2 (per compound) and Stage 3 (reused
  baseline + climbing fetches). Side table avoids the run-row lock (FK child = `FOR KEY SHARE`).
  `execute_run` commits the `stage_N_running` status before running each stage, so a poller sees the
  truly-executing stage and progress aligns with it (auto runs no longer lag a stage behind; guided
  already did this via the approval checkpoint's synchronous commit).
- DTOs (Pydantic v2): `app/schemas/` — `AnalysisRead` strips `stage_results["6"].network_image`
  (the large base64 STRING PPI image) from the status-poll payload via a `field_validator` that
  copies only the touched levels (never mutates the ORM dict, which the export still reads).
- Repositories (only place with SQL): `app/repositories/`
- Pipeline + stages: `app/pipeline/`

## Rules
- All datetimes timezone-aware (`DateTime(timezone=True)` + aware-UTC). A regression test enforces this.
- Organism is **human-only (9606)**, fixed — enforced at Stages 3/4/6 + resolution. Stages 7/8 inherit
  it (they operate on S6 output which is already human-only; no new enforcement point needed).
- External calls only to the fixed scientific-API allow-list; honor each API's verified contract (pagination,
  field names, throttle) per the spec.
- TDD for load-bearing logic (identity, validation, stage math, gating).

## Run
- `uv sync`; `uv run uvicorn app.main:app --reload`; `uv run pytest`.
- Emit the OpenAPI snapshot (codegen input): `uv run python scripts/dump_openapi.py`.
