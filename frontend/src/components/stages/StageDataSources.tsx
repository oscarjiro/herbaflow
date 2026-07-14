import { STAGE_SOURCES, USER_PROVIDED_SOURCES } from "../../contract";
import { Eyebrow } from "@/components/ui/editorial";

export function StageDataSources({
  stage,
  userProvided = false,
  contributingSources,
}: {
  stage: number;
  userProvided?: boolean;
  /**
   * Names of the data sources that actually contributed to this run's stage result (emitted by
   * the backend, e.g. Stage 1's `contributing_sources`). When provided, the static source list is
   * filtered to just these, so a source that contributed nothing this run is not shown. Omit (or
   * pass null/undefined) to fall back to the full static list — the behavior for stages that do
   * not emit per-run provenance and for legacy runs.
   */
  contributingSources?: string[] | null;
}) {
  const staticSources =
    userProvided && USER_PROVIDED_SOURCES[stage]
      ? USER_PROVIDED_SOURCES[stage]
      : STAGE_SOURCES[stage];
  const sources =
    contributingSources != null && !userProvided
      ? (staticSources ?? []).filter((s) => contributingSources.includes(s.name))
      : staticSources;
  if (!sources || sources.length === 0) return null;
  return (
    <div
      className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-sm [color:var(--hf-fg-3)]"
      aria-label="Data sources"
    >
      <Eyebrow>Data sources</Eyebrow>
      <ul className="m-0 flex list-none flex-wrap gap-x-1.5 gap-y-0.5 p-0">
        {sources.map(({ name, url }, idx) => (
          <li key={name} className="flex items-center gap-1.5">
            {url ? (
              <a
                href={url}
                target="_blank"
                rel="noreferrer"
                className="underline underline-offset-2 transition-colors hover:[color:var(--hf-fg-2)]"
              >
                {name}
              </a>
            ) : (
              <span>{name}</span>
            )}
            {idx < sources.length - 1 && (
              <span aria-hidden className="[color:var(--hf-fg-4)]">
                ·
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
