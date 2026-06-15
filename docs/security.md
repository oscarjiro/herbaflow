# Security

This document describes how the Herbaflow backend protects itself and its users. It is written
for a general reader: every term is defined the first time it appears, and each measure is shown
with a short snippet of the real code that implements it (file and line). External standards are
named so a formal reference can be attached later; the in-text marker `[needs citation]` flags
where the thesis should add one.

## 1. Posture and threat model

Herbaflow is an open research tool. It has no user accounts and no login, by deliberate design.
Anyone who can reach the service can run an analysis. There is no private data to guard, no
per-user ownership of results, and nothing that one user could see that another should not. Stating
this plainly is itself the honest first step: confidentiality and per-user authorization are out of
scope on purpose, not by oversight.

That choice has a clear cost and a clear benefit. The benefit is simplicity: no password storage,
no session tokens, no account-recovery flow, and therefore none of the large class of bugs those
mechanisms introduce. The cost is that the service cannot lean on "is this user allowed?" as a line
of defense, because there are no users. So the security boundary sits elsewhere, and the effort
concentrates on four concrete jobs:

- **Bound abuse.** With no login to throttle a single account, the load is carried by per-request
  limits: a cap on request body size and a per-IP rate limit.
- **Refuse malformed input safely.** Every input is checked against an allow-list (a fixed set of
  permitted values or shapes) and is treated as opaque data, never executed.
- **Never leak internals.** Errors return a clean, structured message. Stack traces, file paths,
  and internal exception text never reach the client.
- **Do not let the browser be tricked.** Response headers and output encoding stop the browser from
  being steered into running attacker-supplied content.

The database is protected independently of the application, at the platform layer: row-level
security denies all access by default, and the auto-generated REST data interface is off. Even if
the application were bypassed, the database does not hand data to an anonymous caller.

## 2. Applied measures

Each measure below states the risk in plain words, how Herbaflow handles it, the real code that
does so, and the external standard it follows.

### 2.1 Cross-origin requests (CORS)

A web browser will, by default, let a page from site A make a background request to site B and read
the response only if site B explicitly says site A is allowed. This permission system is called CORS
(Cross-Origin Resource Sharing). If the backend answered "any site is allowed" (the wildcard `*`),
then any web page anywhere could call the API from a visitor's browser and read the result. Herbaflow
instead names the exact origins it trusts, as an explicit allow-list.

```python
# backend/app/main.py:67
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

The allowed origins come from configuration, never a wildcard:

```python
# backend/app/config.py:36
@property
def cors_origins_list(self) -> list[str]:
    """Allowed browser origins for CORS (comma-separated in the environment)."""
    return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
```

CORS is registered last so that every response, including a request that is short-circuited with a
413 or 429, still carries the CORS headers (a browser hides the body of a response that lacks them).

References: OWASP Cheat Sheet Series, Cross-Site Request Forgery Prevention and the HTML5 / CORS
guidance. `[needs citation]`

### 2.2 Security response headers

A browser decides how to treat a response partly from headers the server sends. A few small headers
remove well-known footguns. `X-Content-Type-Options: nosniff` stops the browser from guessing
(sniffing) a response's content type and, for example, running as a script something the server sent
as plain text. `Referrer-Policy: no-referrer` stops the browser from telling a third-party site
which Herbaflow URL the user came from. `X-Frame-Options: DENY` together with the
`Content-Security-Policy: frame-ancestors 'none'` directive stops any other site from embedding
Herbaflow inside a hidden frame and tricking a user into clicking it (clickjacking). A
Content-Security-Policy (CSP) is a server instruction that restricts what the browser may load or
do; `frame-ancestors 'none'` is the one CSP directive that is meaningful for a JSON API. The full
document-level CSP belongs to the page-serving layer and is set there.

```python
# backend/app/security.py:44
async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
    return response
```

The headers are set on every response, including error responses, and are constant (no configuration
needed).

References: OWASP Secure Headers Project; OWASP Cheat Sheet Series, Content Security Policy. `[needs
citation]`

### 2.3 Request payload-size cap

If the service accepted a request body of any size, a single huge upload could exhaust memory before
the application even looked at it. Herbaflow rejects any request whose declared body size is over a
configurable ceiling, before the handler reads it. The default ceiling is 1 MB and is overridable
from the environment.

```python
# backend/app/security.py:65
async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > self.max_bytes:
                return problem_json(
                    413,
                    "Payload Too Large",
                    f"Request body exceeds the {self.max_bytes}-byte limit.",
                )
        except ValueError:
            pass  # malformed header, let the handler and validation deal with it
    return await call_next(request)
```

An oversized request is answered with HTTP 413 (Payload Too Large) in the same structured error
shape as everything else. The size guard for a chunked request that declares no length is left to
the host or proxy layer.

References: OWASP Cheat Sheet Series, Denial of Service. `[needs citation]`

### 2.4 Per-IP rate limiting

Because there is no login, the natural unit to throttle is the caller's network address (IP
address). Herbaflow limits how many requests one IP may make in a window. The most expensive route,
`POST /analyses`, has the tightest budget: every call fans out to external scientific APIs and
spawns a multi-step pipeline, so it is capped at 5 per minute. The two validation routes get 20 per
minute, and a global default of 120 per minute applies to everything else. All budgets come from
configuration, and the whole feature can be switched off cleanly for local runs and tests.

```python
# backend/app/security.py:18
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_default],
    enabled=settings.rate_limit_enabled,
)
```

```python
# backend/app/config.py:29
max_request_bytes: int = 1_048_576  # 1 MB request-body cap
rate_limit_enabled: bool = True
rate_limit_default: str = "120/minute"
rate_limit_create: str = "5/minute"
rate_limit_validate: str = "20/minute"
```

A caller over the budget gets HTTP 429 (Too Many Requests) in the structured error shape, with a
`Retry-After` header. One deployment note: behind a reverse proxy the real caller's address arrives
in the `X-Forwarded-For` header, so the server must be run with proxy-header trust enabled,
otherwise every caller looks like the proxy and shares one budget.

References: slowapi documentation; OWASP Cheat Sheet Series, Denial of Service. `[needs citation]`

### 2.5 Parameterized queries (no string-built SQL)

SQL injection happens when user text is pasted directly into a database query string, so that input
like `'; DROP TABLE ...` becomes part of the command. Herbaflow never builds SQL by string
concatenation. All database access goes through a single repository layer that uses the SQLAlchemy
query builder, which sends the user value as a separate bound parameter. The database treats that
value strictly as data, never as command text.

```python
# backend/app/repositories/compound.py:21
async def get_by_key(self, canonical_key: str) -> Compound | None:
    stmt = select(Compound).where(Compound.canonical_key == canonical_key)
    return (await self.session.execute(stmt)).scalar_one_or_none()
```

Here `canonical_key` is bound, not interpolated; a value such as `' OR 1=1 --` is looked up as a
literal string and simply matches nothing. The repository layer is the only place in the codebase
that issues SQL.

References: OWASP Cheat Sheet Series, SQL Injection Prevention. `[needs citation]`

### 2.6 Allow-list input validation (safety and correctness)

Validation has two faces, and Herbaflow covers both for every input.

**Safety** means a malformed or malicious value cannot be weaponized. Identifiers such as plant,
compound, and target ids are typed as UUIDs at the schema boundary, so an injection string is
rejected as the wrong type before it ever reaches a query. Free-text inputs, such as a pasted
chemical structure, are canonicalized and looked up; unrecognized text becomes an opaque rejection,
never a query fragment and never a server crash.

**Correctness** means the input is valid for the scientific domain: the right type, a value inside
the allowed range, an allowed choice from a fixed vocabulary, a reference to an entity that actually
exists, and any cross-field rule satisfied. Crucially, every rejection carries an honest, specific
reason. Nothing is dropped silently. When a pasted line cannot be resolved, the service records why,
keyed to the 1-based line number, and returns it:

```python
# backend/app/services/input_validation.py:62
if not structure.is_inchikey(token):
    logger.info("  rejected %r: invalid InChIKey format", item.value)
    failed.append(
        FailedInput(value=item.value, reason="invalid InChIKey format", line=idx)
    )
    continue
```

The authoritative boundary is the backend: Pydantic schemas enforce types, the shared contract is
the single source for ranges and allowed choices, the services confirm that referenced entities
exist, and `app/services/input_validation.py` resolves free text against an allow-list with a
per-line reason for every failure. The frontend performs the same checks live as the user types, but
that layer is advisory only (a convenience), derived from the same contract; it never replaces the
backend check. The frontend live-validation bounds are read from the shared contract in
`frontend/src/contract/index.ts`, and the generated request schemas in `frontend/src/api/zod.gen.ts`
provide type-level validation.

References: OWASP Cheat Sheet Series, Input Validation. `[needs citation]`

### 2.7 Error sanitization (RFC 9457 problem+json)

When something goes wrong, a careless server can hand the caller a stack trace, a file path, or the
text of an internal exception, which together hand an attacker a map of the system. Herbaflow returns
one consistent, machine-readable error shape and nothing internal. The format is RFC 9457, the
standard for an `application/problem+json` error document: a small object with a `type`, `title`,
`status`, and optional `detail`.

```python
# backend/app/errors.py:106
async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return _problem(500, "Internal Server Error", "An internal error occurred.", "about:blank")
```

The full exception, with its stack trace, is logged on the server for the operator; the client sees
only the generic 500 message. The same builder produces every other error in the system (404, 409,
413, 422, 429, and the 503 returned when the database is unreachable), so there is exactly one error
shape and no path that leaks internals.

References: RFC 9457 (Problem Details for HTTP APIs). `[needs citation]`

### 2.8 Download-filename allow-list

A download endpoint that builds a file path from a name in the URL is a classic path-traversal
target: a caller sends `../../etc/passwd` and reads files outside the intended folder. The Herbaflow
export endpoint `GET /export/{filename}` is structurally immune, because it never builds a filesystem
path at all. The filename in the URL is only used as a key into an in-memory dictionary of
artifacts that were already assembled in memory. A `../` segment is simply a key that is not present,
so it returns 404.

```python
# backend/app/routers/export.py:121
a = await assemble_export(session, analysis_id)
artifact = {**a._network_files(), **a._stage_files()}.get(filename)
if isinstance(artifact, bytes):
    return Response(artifact, media_type="image/png", headers=_disposition(filename))
if isinstance(artifact, str):
    return Response(artifact, media_type="text/csv", headers=_disposition(filename))
raise NotFoundProblem(f"unknown export artifact {filename!r}")
```

Because there is no path join, traversal is not possible by construction, not merely filtered out.

References: OWASP Cheat Sheet Series, Input Validation (path traversal). `[needs citation]`

### 2.9 Database row-level security and the data interface

The database sits behind the application, but it is also hardened on its own so that a bypass of the
application gains nothing. Two platform controls do this. Row-level security (RLS) is a Postgres
feature where every table can carry policies that decide, row by row, who may read or write; with
RLS enabled and no permissive policy, the default answer is deny. On this project RLS is enabled and
deny-by-default on all public tables. Separately, the platform can expose an auto-generated REST
interface directly onto the database tables; that interface is off, so an anonymous key reaches no
data through it. These are verified live against the database, not assumed. The motivation for
checking both is concrete: a publicly disclosed class of incidents has shown that a misconfigured
RLS policy can expose an entire table to anonymous callers.

References: Supabase documentation, Row Level Security and Securing your API; the
RLS-misconfiguration disclosure CVE-2025-48757. `[needs citation]`

### 2.10 Security-event logging

If nothing is recorded, an operator cannot tell whether the system is being probed or is failing.
Herbaflow logs the security-relevant events through one structured stdout stream: the lifecycle of
each run (creation with its inputs, an idempotent replay, a deletion), every input rejection (as a
422 with a per-field reason), and every dependency outage (a provider 503 or a database-unavailable
503). Unhandled errors are logged with their stack trace on the server while the client sees only the
sanitized message. No secrets, credentials, or full request bodies are ever written to the log. The
logging standard and the exact event list live in `docs/observability.md`.

References: OWASP Cheat Sheet Series, Logging. `[needs citation]`

### 2.11 React output-encoding and the `dangerouslySetInnerHTML` ban

Cross-site scripting (XSS) is when attacker-supplied text is rendered into a page as live HTML or
script and runs in the victim's browser. The frontend framework, React, defends against this by
default: any value placed into the page through normal rendering is escaped, so it is shown as text,
not interpreted as markup. The one common way to defeat that default is React's
`dangerouslySetInnerHTML`, which injects raw HTML. Herbaflow bans it with a lint rule, so the safe
default cannot be silently bypassed.

```javascript
// frontend/eslint.config.js:11
"no-restricted-syntax": [
  "error",
  {
    selector: "JSXAttribute[name.name='dangerouslySetInnerHTML']",
    message: "dangerouslySetInnerHTML is banned (XSS). Render escaped values only.",
  },
],
```

The build fails if anyone introduces the attribute, so every rendered value stays escaped. The full
document-level Content-Security-Policy that further constrains script execution is delivered at the
page-serving layer.

References: OWASP Cheat Sheet Series, Cross-Site Scripting Prevention. `[needs citation]`

## 3. OWASP Top 10:2025 walk-through

The OWASP Top 10 is a widely used, periodically updated list of the most critical web-application
security risks, published by the Open Worldwide Application Security Project (OWASP). Each entry
below states how Herbaflow handles that risk, or why it does not apply, with the reason stated.

### A01 Broken Access Control

The application is open by design: there are no accounts, so there is no per-user access control to
break. The protection that matters here is at the database. Row-level security is deny-by-default on
all public tables and the REST data interface is off, so an anonymous caller reaching the database
directly gets nothing. Verified at the database layer rather than by a unit test.

### A02 Security Misconfiguration

The common misconfigurations are closed: CORS is a named allow-list rather than a wildcard, the
security response headers are set on every response, the payload cap is enforced, configuration and
secrets come from the environment and are never exposed to the client, the database has RLS on and
its data interface off, and errors are sanitized. Covered by the header and payload-cap tests.

### A03 Software Supply Chain Failures

Dependencies are pinned by lockfiles (`uv.lock` for the backend, `pnpm-lock.yaml` for the frontend),
so a build cannot silently pull a different version, and the continuous-integration gates run against
those pinned versions. Honest gap: there is no automated scan for known vulnerabilities in
dependencies yet. The recommended addition is a scheduled audit such as `pip-audit`, `npm audit`, or
Dependabot. `[needs citation]` Not a code control, so no unit test.

### A04 Cryptographic Failures

Low applicability. The application stores no secrets or personal data and performs no cryptography of
its own. Transport encryption (TLS) is provided by the host and the database platform. Documented as
not applicable, with the reason stated; no test.

### A05 Injection

SQL injection is prevented by parameterized queries through the single repository layer (no
string-built SQL), backed by allow-list input validation, and proven by a dedicated SQL-injection
regression test that drives classic attack payloads through the input fields and confirms they
resolve to an honest rejection, never a crash, with the database intact afterward. Cross-site
scripting is prevented by React's default output-encoding plus the `dangerouslySetInnerHTML` lint
ban; the document-level CSP at the serving layer adds defense in depth.

### A06 Insecure Design

The threat boundary is stated as a conscious decision rather than an accident, which is itself the
practice this category asks for. The set of external services the backend calls is a fixed allow-list
of scientific APIs, with no user-supplied URLs, which keeps server-side request forgery risk low.
States fail closed rather than open, and no input is ever dropped silently: every rejection carries a
reason. Covered by the validation tests.

### A07 Authentication Failures

Not applicable by design: there is no authentication, so there are no authentication failures to
have. Cross-site request forgery is also not applicable, because the service uses no cookies or
sessions that a forged request could ride on. The abuse load that authentication would otherwise help
carry is instead carried by the rate limit, the payload cap, and database RLS. No test.

### A08 Software or Data Integrity Failures

Integrity is protected by the lockfiles above, by versioned migration files that record every schema
change, and by a code-generation drift gate that fails the build if the wire contract between
frontend and backend diverges from its single source. Covered by the existing drift gate.

### A09 Security Logging and Alerting Failures

Security-relevant events are logged through one structured stream: run creation, replay, and
deletion, input rejections, and dependency or database outages. Limitation, stated honestly: there is
no automated paging or alerting on those logs, which is acceptable for a research tool but would need
adding for a production deployment. Covered by the existing logging tests.

### A10 Mishandling of Exceptional Conditions

Every error path returns the one RFC 9457 problem+json shape with a sanitized message, no path fails
open, each pipeline step has an explicit failure state rather than a silent continue, and an
unreachable database is mapped to a clean 503 rather than a leaking 500. Covered by the
error-sanitization test.

## 4. Validation coverage

Each external input surface is listed below with, per field, which checks apply and where the
asserting code lives. The two faces are safety (the input cannot be weaponized) and correctness
(right type, in range, allowed value, the referenced entity exists, cross-field rules hold, and every
rejection carries an honest reason).

### Layering

- Pydantic schemas enforce types (UUID, enum, literal, list).
- The shared contract (`app/contracts.py` over the shared contract file) is the single source for
  ranges and allowed values.
- Services enforce existence of referenced entities.
- Schema-level and engine-level validators enforce cross-field and element-wise rules.
- A global body-size cap (`app/security.py`) bounds payload size, and the RFC 9457 error mapping
  (`app/errors.py`) covers the safety envelope for every surface.

### Surface 1: `POST /analyses` (AnalysisCreate)

Schema `app/schemas/analysis.py` (lines 31-83); existence in `app/services/analysis.py` (lines
65-211).

| Field | Checks | Evidence |
|---|---|---|
| analysis_name | type (str or null); body cap | schema:32; security.py:66-73 |
| plant_input_mode | enum (closed vocabulary), off-list rejected 422; cross-field | schema:33; schema:20-23; schema:44-69 |
| disease_input_mode | enum, off-list rejected 422; cross-field | schema:34; schema:26-28; schema:71-82 |
| plant_ids | type list of UUID; max-count from contract; existence; required or forbidden by mode | schema:35; analysis.py:83-88; analysis.py:48-67 |
| disease_id | type UUID or null; existence; required or forbidden by mode | schema:36; analysis.py:94-98; schema:71-82 |
| mode | enum, off-list rejected 422 | schema:37; schema:15-17 |
| manual_compound_ids | type list of UUID; entity cap 422; existence; required or forbidden by mode | schema:38; analysis.py:89-90, 197-211 |
| manual_target_ids | type list of UUID; entity cap 422; existence; required or forbidden by mode | schema:39; analysis.py:91-92, 205-211 |
| manual_disease_target_ids | type list of UUID; entity cap 422; existence; required or forbidden by mode | schema:40; analysis.py:99-102, 205-211 |
| plant_label | type str or null, max length 200; allowed only in a manual plant mode | schema:41; schema:56-57 |
| disease_label | type str or null, max length 200; allowed only in the manual disease mode | schema:42; schema:74-75 |

A user-provided stage that resolves to zero usable entities rejects the whole create with a 422
(analysis.py:132-141), so nothing is silently dropped. Coverage: all covered.

### Surface 2: `POST /compounds/validate` (resolve_compounds)

Schema `app/schemas/compound.py` (lines 11-30); resolution `app/services/input_validation.py`
(lines 47-150).

| Field | Checks | Evidence |
|---|---|---|
| inputs[].type | literal (smiles or inchikey or null), off-list rejected 422 | compound.py:12 |
| inputs[].value | type str; body cap; existence (resolved database-first, then PubChem); unresolved becomes a per-line failure with a reason, never a silent drop, never SQL, never a crash | compound.py:13; input_validation.py:61-139 |

Every rejected line gets a `FailedInput` with a reason and a 1-based line index
(input_validation.py:64-66, 72-73, 130-138). Coverage: all covered.

### Surface 3: `POST /targets/validate` (resolve_targets)

Schema `app/schemas/target.py` (lines 21-36); resolution `app/services/input_validation.py`
(lines 245-334) plus `resolve_target_accession` (lines 153-232).

| Field | Checks | Evidence |
|---|---|---|
| inputs[].type | literal (symbol or uniprot or null), off-list rejected 422 | target.py:22 |
| inputs[].value | type str; body cap; existence (classified, then HGNC normalization, then database-first, then UniProt for human records only); a strict accession grammar gates the lookup so non-grammar text short-circuits without a network call; each miss becomes a per-line failure with a precise reason | target.py:23; input_validation.py:35-37, 183-184, 264-330 |

Failures distinguish invalid format, not a UniProt accession, no human record, an InChIKey pasted
into the target box, and an unrecognized identifier, each with its own reason and a 1-based line
(input_validation.py:41-44, 276-330). Coverage: all covered.

### Surface 4: `POST /analyses/{id}/reset-from/{stage}` (ResetFromRequest plus override validation)

Schema `app/schemas/analysis.py` (lines 86-94); path stage handled in `app/routers/analyses.py`
(lines 65-78); override validation in `app/pipeline/engine.py` (lines 293-353); reset guards in
`engine.reset_from` (lines 356-462).

| Field or param | Checks | Evidence |
|---|---|---|
| {stage} (path) | type int; must be runnable, computed, and within progress, else 422; a frozen stage refuses a parameter redo | engine.py:397-412 |
| parameters (body) | type dict; an unknown parameter key rejects 422; only the entry matching the target stage is forwarded | schema:94; engine.py:303-304; router:73 |
| numeric params | type integer-versus-float and not-a-number checks; minimum, exclusive-minimum, and maximum from the contract, out-of-range rejected 422 | engine.py:341-353 |
| boolean params | must be boolean | engine.py:306-308 |
| string params | must be string; contract enum enforced, off-list rejected 422 | engine.py:313-319 |
| array params | must be a list of strings, with a minimum-items check and an element-wise allowed-value check that lists the bad values | engine.py:323-339 |
| ppi.min_confidence | numeric type checked; see the note below | engine.py:341-353 |

Note on `ppi.min_confidence`: this is the only parameter whose contract gives a numeric set of
allowed values, and the numeric branch of the override validator does not currently enforce that set
(an off-tier value such as 0.55 is accepted). This is not a safety hole: the downstream value it
produces is always in a valid range and is handled gracefully, so the input cannot be weaponized.
Whether the numeric set is a hard constraint or a user-interface preset is a contract-owner decision,
so it is recorded as a review item rather than force-fixed. Coverage: covered except this one review
item.

### Surface 5: `POST /analyses/{id}/stages/{stage}/edit` (StageEditRequest plus edit_stage)

Schema `app/schemas/analysis.py` (lines 97-101); service `app/services/analysis.py` `edit_stage`
(lines 352-489).

| Field | Checks | Evidence |
|---|---|---|
| {stage} (path) | type int; must be an editable entity stage and must be computed, else 422 | analysis.py:369-371, 386-388 |
| add | type list of UUID; net-addition entity cap 422; existence; a settled run is refused 409 | analysis.py:391-413, 380-383 |
| remove | type list of UUID; an edit may never empty a stage, else 422 | analysis.py:459-465 |

Unknown ids to add reject 422 with the precise field; removing the last entity rejects 422; editing
a non-entity or not-yet-computed stage rejects 422; a running run is refused 409. Coverage: all
covered.

### Surface 6: `GET /analyses/{id}/export/{filename}` (assembled-filename allow-list)

Router `app/routers/export.py` `export_artifact` (lines 111-127); allow-list source
`app/services/export.py` (lines 38-53).

| Field | Checks | Evidence |
|---|---|---|
| {analysis_id} | type UUID; 404 if the run is missing, 409 if it is not complete | export.py:142-146 |
| {filename} (path) | looked up in the assembled allow-list; the name is never used to build a filesystem path, so a `../` segment is simply a missing key and returns 404, and traversal is impossible by construction | export.py:122-127 |

Coverage: all covered. An explicit traversal-string test would add belt-and-suspenders coverage but
is not required, because the route is structurally traversal-proof.

### Summary

Surfaces 1, 2, 3, 5, and 6 are fully covered with cited asserting code. Surface 4 is fully covered
except the single review item above (the numeric allowed-set on `ppi.min_confidence`), which is not a
safety issue and is a contract-owner design decision. No unambiguous gap requiring a code change was
found.

## 5. Testing

Each control is asserted by an automated test. Integration tests run against a real Postgres instance
where that adds meaning (the injection test); unit tests cover the rest.

| Control | Test |
|---|---|
| Security response headers on normal and error responses | `tests/test_security_headers.py` |
| Payload-size cap (over the cap returns 413, under passes) | `tests/test_security_middleware.py` |
| Per-IP rate limiting (the create and validate budgets return 429; the flag disables it) | `tests/test_rate_limit_endpoints.py` |
| Parameterized queries against SQL injection | `tests/integration/test_sql_injection.py` |
| Error sanitization (no traceback or internal detail leaks) | `tests/test_security_error_message.py`, `tests/test_errors.py` |
| Security and limit settings (CORS allow-list, configured budgets) | `tests/test_security_settings.py` |
| Download-filename allow-list (unknown or undrawable artifact returns 404) | `tests/test_export.py` |

## 6. References and needs-citation

The standards and tools named in this document are listed here for the formal reference list. Each is
marked `[needs citation]` where the thesis should attach a full citation.

- OWASP Top 10:2025 (Open Worldwide Application Security Project). `[needs citation]`
- OWASP Cheat Sheet Series: Input Validation; SQL Injection Prevention; Cross-Site Scripting
  Prevention; Denial of Service; and the OWASP Secure Headers Project. `[needs citation]`
- RFC 9457, Problem Details for HTTP APIs. `[needs citation]`
- slowapi documentation (the per-IP rate-limiting library). `[needs citation]`
- Supabase documentation: Row Level Security; Securing your API. `[needs citation]`
- CVE-2025-48757, the row-level-security misconfiguration disclosure that motivates verifying both
  RLS and the data interface. `[needs citation]`
