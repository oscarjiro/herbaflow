export function AboutSphere() {
  return (
    <div className="ab-shape ab-shape-sphere" aria-hidden="true">
      <svg viewBox="0 0 400 400" strokeWidth={1} fill="none" stroke="currentColor">
        <circle cx="200" cy="200" r="150" />
        <ellipse cx="200" cy="200" rx="150" ry="55" />
        <ellipse cx="200" cy="200" rx="150" ry="108" strokeDasharray="3 7" />
        <ellipse className="ab-meridian" cx="200" cy="200" rx="132" ry="150" />
        <ellipse
          className="ab-meridian"
          cx="200"
          cy="200"
          rx="96"
          ry="150"
          style={{ animationDelay: "-2s" }}
        />
        <ellipse
          className="ab-meridian"
          cx="200"
          cy="200"
          rx="55"
          ry="150"
          style={{ animationDelay: "-4s" }}
        />
        <ellipse
          className="ab-meridian"
          cx="200"
          cy="200"
          rx="18"
          ry="150"
          strokeDasharray="3 7"
          style={{ animationDelay: "-6s" }}
        />
        <circle cx="200" cy="200" r="3" fill="currentColor" stroke="none" />
      </svg>
    </div>
  );
}

export function AboutRings() {
  return (
    <div className="ab-shape ab-shape-rings" aria-hidden="true">
      <svg viewBox="0 0 300 300" strokeWidth={1} fill="none" stroke="currentColor">
        <circle cx="150" cy="150" r="40" />
        <circle cx="150" cy="150" r="72" />
        <circle cx="150" cy="150" r="104" strokeDasharray="2 6" />
        <circle cx="150" cy="150" r="136" />
      </svg>
    </div>
  );
}
