# Architecture

Violarr is a thin, single-container adapter between an ICVDB PostgreSQL
snapshot and Torznab-compatible clients. v1.1 adds a WebUI and persistent
configuration without changing the v1.0 runtime boundary.

## Runtime topology

```text
┌──────────────────────────────────────────────────────────┐
│ Violarr container (operational alias: icvdb-torznab)     │
│                                                          │
│  :8000 FastAPI                                           │
│    ├── /         Vue WebUI                               │
│    ├── /webapi   settings, status, updater, Prowlarr     │
│    └── /api      Torznab XML                             │
│                     │                                    │
│  PostgreSQL 16 ◄────┘  127.0.0.1:5432 only              │
│                                                          │
│  /data                                                   │
│    ├── postgres/                                         │
│    └── state/{settings.json,snapshot-version}            │
└──────────────────────────────────────────────────────────┘
```

Only port `8000` is published. PostgreSQL is not exposed, and the application
does not use a Docker socket, Redis, a separate settings database, or a second
runtime container.

## Modules

| Module                  | Responsibility                                                                              |
| ----------------------- | ------------------------------------------------------------------------------------------- |
| `app.py`                | FastAPI lifecycle, Torznab queries/XML, result-processing integration, static WebUI serving |
| `settings.py`           | Schema-v1 validation, atomic persistence, environment precedence, public secret masking     |
| `result_processor.py`   | Italian presets and bounded custom score/exclusion rules                                    |
| `webapi.py`             | Same-origin JSON status, settings, processing, Prowlarr, and diagnostics endpoints          |
| `diagnostic_models.py`  | Strict bounded diagnostic inputs and report-v1 response contracts                           |
| `search_diagnostics.py` | Optional request-scoped stage/window/candidate collection and structural redaction          |
| `search_monitor.py`     | Failure-isolated Torznab observation and bounded thread-safe in-memory history              |
| `prowlarr.py`           | `X-Api-Key` client, Generic Torznab schema derivation, test/create/idempotency              |
| `snapshot_updater.py`   | Snapshot discovery, validation, candidate restore, switch, rollback, updater state          |
| `frontend/`             | Vue 3 WebUI source and shared product design tokens                                         |
| `entrypoint.sh`         | PostgreSQL bootstrap, first snapshot restore, Uvicorn lifecycle, clean shutdown             |

## Image build and startup

The Dockerfile has a Node build stage for `frontend/`. Only generated production
assets are copied into the PostgreSQL/Python runtime at `/app/frontend-dist`.
FastAPI registers `/api` and `/webapi` before low-priority static and SPA fallback
routes. Reserved API, OpenAPI, docs, and ReDoc paths cannot fall through to the
SPA.

Startup preserves the v1.0 sequence:

```text
initialize or reuse /data/postgres
        ↓
start PostgreSQL and wait for readiness
        ↓
create application database when needed
        ↓
bootstrap latest snapshot when no installed state exists
        ↓
start FastAPI and the periodic updater
```

The runtime integration has been validated with a local image build, container
startup, capabilities request, and a real PostgreSQL-backed search.

## Request flows

### Torznab

```text
/api query parameters
        ↓
normalized values and parameterized psycopg SQL
        ↓
optional result processing
        ↓
ElementTree Torznab RSS serialization
```

`t=search`, `t=movie`, and `t=tvsearch` retain the v1.0 parameters, categories,
limits, offset behavior, and XML item shape. The default `unfiltered` preset
passes `limit` and `offset` directly to the database.

### WebUI and WebAPI

```text
browser → Vue static assets → same-origin /webapi
                              ├── settings store
                              ├── updater state/reconfigure
                              ├── database probe
                              └── Prowlarr client
```

The aggregate status endpoint does not make a live Prowlarr request. Live status
is fetched by the focused Prowlarr status endpoint and retained only as an
in-process summary.

### Prowlarr

The client sends `X-Api-Key` to Prowlarr. It reads
`/api/v1/indexer/schema`, selects the Generic Torznab `Torznab` implementation,
deep-clones the schema resource, names it `Violarr`, and fills `baseUrl`,
`apiPath`, and the blank Torznab `apiKey` field. Add checks existing Torznab
resources by normalized origin/path before asking Prowlarr to test and create the
resource, making repeated requests idempotent.

The focused Prowlarr status route reports remote failures in an HTTP `200` status
payload. It preserves secret-safe specific client errors, but replaces any error
containing the configured key or traceback text with `Prowlarr request failed`.
The POST test/create routes return that stable detail with HTTP `502` for remote
failures. API keys and tracebacks are not returned.

## Settings model

Settings use schema version 1 and default to:

- automatic updates enabled every 86400 seconds;
- `unfiltered` result processing with no custom rules;
- empty Prowlarr URL, Indexer URL, and API key.

Effective precedence is:

```text
built-in defaults < /data/state/settings.json < runtime environment
```

`SettingsStore.save` writes a temporary file in the state directory, flushes and
fsyncs it, then replaces `settings.json` atomically. WebUI updates begin from
persisted values so runtime overrides are not accidentally copied to disk.

Public settings replace `api_key` with `api_key_configured`. Omitting the key on
update preserves the stored value, a non-empty value replaces it, and an empty
value clears it. An environment-provided key is effective but never persisted.

Supported settings overrides are `DB_AUTO_UPDATE`, `DB_UPDATE_INTERVAL`,
`ICVDB_RESULT_PRESET`, `ICVDB_PROWLARR_URL`, `ICVDB_PROWLARR_API_KEY`,
`PROWLARR_API_KEY`, and `PROWLARR_INDEXER_URL`. `PROWLARR_API_KEY` wins when both
API-key aliases are set.

## Result pipeline

Rows have the processing fields `title`, `size`, `seeders`, and `provider`.

- `unfiltered` preserves database order.
- `italian_only` keeps exact title tokens `ITA`, `ITALIAN`, or `ITALIANO`.
- `italian_preferred` scores those explicit markers at 100 and exact `MULTI` or
  `DUAL` tokens at 25.
- `custom` removes rows matching enabled exclusion rules, then stably ranks the
  remainder by summed score rules.

Rules are structured and bounded: no regular expressions or scripts, at most
100 rules, text values up to 512 characters, finite numbers, and score magnitude
up to 1000. Text operators compare Unicode case-folded values; null text matches
only `not_contains`. Numeric operators require finite non-boolean values on both
sides, so null and non-finite row values never match.

Processed pagination operates on fixed, non-overlapping 1000-row database
windows. Ranking is local to each window, equal scores preserve original order,
and filtered pages are not backfilled from later windows.

This pipeline affects only ICVDB's XML response. It cannot guarantee downstream
Radarr/Sonarr selection. Hard filters hide results from Prowlarr entirely.

## Search diagnostics and request monitoring

`/diagnostics` in the Vue WebUI defaults to Search. Its simple/advanced form sends
`POST /webapi/diagnostics/search` to the same `execute_search()` path as `/api`:
normalization → database window lookup → existing result processing/pagination →
ElementTree serialization and validation of the actual RSS root and item count.
There is no second SQL or filtering implementation. The collector is scoped through
a `ContextVar` and does not change normal ordering, ignored parameters, subtitle
correction, settings precedence, or snapshot-switch behavior. `cat` remains accepted
but unused by queries; TV searches still ignore `tmdbid`.

Report v1 carries original/normalized allowlisted parameters, selected strategy,
four stage statuses/timings, inspected windows, processing settings/indexed rules,
separate serialization settings, app/snapshot versions, bounded candidate metadata,
safe errors, truncation/replayability flags and limitations. Counts are window-local,
not database totals. Candidates may be excluded, retained outside the page, selected
for serialization, or returned; selected rows become returned only after actual XML
validation succeeds. Returned language is read from XML, separately from the
subtitle-correction flag used during processing. Stage failures produce partial
reports with HTTP `200`: consumers must inspect statuses/errors, not HTTP success.
Invalid diagnostic JSON produces a safe `422`; maintenance middleware can return
`503` before diagnostic handlers run.

Requests uses `GET/PUT /webapi/diagnostics/monitoring` and
`GET/DELETE /webapi/diagnostics/requests`. Monitoring defaults off and is runtime-only.
A lock-protected buffer stores at most 100 arrival-newest-first metadata entries;
slow older completions cannot evict newer arrivals. No release sets, headers, client
addresses, keys, magnets, SQL, raw exceptions or database configuration are retained.
Observation faults do not replace the original Torznab response. Disabling capture
preserves existing history; clearing removes it; restart clears history and state.
The browser polls sequentially every five seconds only in Requests and aborts/guards
pending refreshes when leaving, clearing or toggling. It cancels outstanding work on
unmount so stale refreshes cannot restore cleared data.

Replay is a fresh diagnostic POST using a replayable entry's **original** parameters,
including intentionally ignored fields. Current settings and the current local
snapshot apply; historical conditions are not reconstructed. Diagnostic executions
and replays are not added to incoming-request history.

Export is browser-local JSON, not a new server endpoint or external service. The UI
projects the versioned allowlist at every level, applies structural redaction, bounds
arrays/text and rejects downloads over 4 MB. It presents the exact export preview
and a sharing warning before download. Titles, terms and rule values can still be
sensitive: structural sanitization does not make a report anonymous. Existing
trusted-network/authenticated-proxy deployment requirements apply to execution,
monitoring controls/history and reports, since these endpoints have no authentication.
No settings migration, persistent logs, new containers or privileged remote execution
are introduced. Diagnostics cannot compare live Stremio content or identify downstream
Sonarr/Radarr/Prowlarr rejection reasons.

## Snapshot invariants

Snapshot metadata comes from the configured GitHub latest-release endpoint. The
updater selects a `.dump` asset and requires its GitHub `sha256:` digest.

Before switching, it verifies:

1. downloaded SHA256;
2. custom dump readability with `pg_restore --list`;
3. restore completion with `--exit-on-error` into `icv_db_candidate`;
4. candidate connectivity and presence of user tables.

The active `icv_db` remains available during download, inspection, restore, and
candidate validation. Maintenance mode begins only for the database rename and
post-switch validation; HTTP requests then receive `503` with `Retry-After: 5`.

```text
icv_db           → icv_db_previous
icv_db_candidate → icv_db
```

After successful final validation, the updater atomically writes
`/data/state/snapshot-version` and removes the previous database. A failed final
validation attempts rollback from `icv_db_previous`. Earlier failures never
modify the active database.

## Security boundaries

- WebUI, WebAPI, and Torznab currently have no authentication.
- `apikey` is accepted for Torznab compatibility but not validated.
- Deploy port `8000` only on a trusted LAN or behind an authenticated proxy.
- Prowlarr API keys are masked in normal reads and sanitized from WebAPI errors.
- Stored settings are not encrypted; protect the `/data` volume.
- PostgreSQL binds internally to `127.0.0.1:5432`.
- All HTTP-derived SQL values use psycopg parameter binding.
- XML is built with `xml.etree.ElementTree`, not string concatenation.

## Upgrade compatibility

The published image is `ghcr.io/xbit18/violarr`.

v1.1 preserves the v1.0 Compose service and container name `icvdb-torznab`,
named volume `icvdb_torznab_data`, image port, PostgreSQL 16 cluster location,
`/data` volume, `/data/state/settings.json`, schema version 1, `ICVDB_*` and
`DB_*` environment variables, `/api` and `/webapi` routes, snapshot-version
state, snapshot source `xbit18/icvdb-snapshots`, bootstrap/update model, and XML
contract. These legacy technical identifiers intentionally remain stable for
existing volumes, configuration, automation, and Prowlarr URLs. An existing
v1.0 volume should be reused directly; v1.1 adds `settings.json` with defaults
on first access.

Never remove the volume during an application-image upgrade. The compatibility
contract follows the preserved implementation invariants and is covered by
container contract tests.
