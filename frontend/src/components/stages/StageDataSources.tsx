import { STAGE_SOURCES, USER_PROVIDED_SOURCES } from "../../contract";

export function StageDataSources({
  stage,
  userProvided = false,
}: {
  stage: number;
  userProvided?: boolean;
}) {
  const sources =
    userProvided && USER_PROVIDED_SOURCES[stage]
      ? USER_PROVIDED_SOURCES[stage]
      : STAGE_SOURCES[stage];
  if (!sources) return null;
  return (
    <div className="stage-data-sources hf-muted" aria-label="Data sources">
      <span className="stage-data-sources__label">Data sources</span>
      <ul>
        {sources.map(({ name, url }) => (
          <li key={name}>
            {url ? (
              <a href={url} target="_blank" rel="noreferrer">
                {name}
              </a>
            ) : (
              <span>{name}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
