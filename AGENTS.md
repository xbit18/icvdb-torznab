# AGENTS.md

## Project overview

Violarr is a self-hosted Torznab indexer for ICVDB.

It exposes the ICVDB PostgreSQL dataset to Torznab-compatible clients such as Prowlarr and provides a Vue WebUI for configuration, result processing, database updates, and Prowlarr integration.

Public repository:

```text
xbit18/violarr
```

Published Docker image:

```text
ghcr.io/xbit18/violarr
```

Violarr does not scrape torrent websites, download torrents, manage media libraries, or maintain the upstream ICVDB database.

## Runtime architecture

Violarr is intentionally a **single-container application**.

The container includes:

- FastAPI;
- the compiled Vue WebUI;
- PostgreSQL 16;
- the ICVDB database;
- the automatic snapshot updater.

Runtime topology:

```text
┌─────────────────────────────────────────────┐
│ Violarr container                           │
│                                             │
│ :8000 FastAPI                               │
│   ├── /         Vue WebUI                   │
│   ├── /webapi   JSON API                    │
│   └── /api      Torznab XML API             │
│                    │                        │
│ PostgreSQL 16 ◄────┘                        │
│ 127.0.0.1:5432 only                         │
│                                             │
│ /data                                       │
│   ├── postgres/                             │
│   └── state/                                │
│       ├── settings.json                     │
│       └── snapshot-version                  │
└─────────────────────────────────────────────┘
```

Only port `8000` is published.

PostgreSQL is internal to the container and must not normally be exposed.

There is no separate PostgreSQL Compose service, Redis instance, Docker socket, or settings database.

## Main technologies

Backend:

- Python 3.12
- FastAPI
- Uvicorn
- psycopg 3
- PostgreSQL 16

Frontend:

- Vue 3
- TypeScript
- Vite
- Vue Router
- Vitest
- ESLint
- Prettier

Documentation:

- VitePress

Infrastructure:

- Docker
- Docker Compose
- GitHub Actions
- Release Please
- GHCR

## Important files

### Backend

- `app.py` — FastAPI lifecycle, Torznab endpoints, database queries, XML generation, static frontend serving
- `webapi.py` — WebUI JSON API
- `settings.py` — settings validation, persistence, environment overrides, secret masking
- `result_processor.py` — result filtering and ranking
- `prowlarr.py` — Prowlarr API integration
- `snapshot_updater.py` — snapshot discovery, download, validation, restore, switch, rollback
- `version.py` — application version handling
- `entrypoint.sh` — PostgreSQL bootstrap and application startup

### Frontend

- `frontend/` — Vue WebUI source
- `frontend/src/` — application code
- `frontend/package.json` — frontend scripts and dependencies

### Documentation

- `README.md` / `README.en.md` — project landing documentation
- `ARCHITECTURE.md` — detailed architecture and runtime behavior
- `docs/` — VitePress documentation site

### Infrastructure

- `Dockerfile` — production image
- `docker-compose.yml` — default deployment
- `requirements.txt` — Python runtime dependencies
- `requirements-dev.txt` — Python development dependencies
- `.github/workflows/ci.yml` — validation pipeline
- `.github/workflows/release-please.yml` — automated release management
- `.github/workflows/publish-image.yml` — multi-architecture GHCR publishing
- `release-please-config.json` — Release Please configuration
- `.release-please-manifest.json` — current released version
- `.githooks/` — local Git hooks
- `ruff.toml` — Python lint/format configuration
- `commitlint.config.mjs` — Conventional Commit rules

## Compatibility contracts

Use **Violarr** for public naming.

The following legacy technical identifiers are intentional compatibility contracts and must not be renamed casually:

- container/service name `icvdb-torznab`;
- Docker volume `icvdb_torznab_data`;
- persistent mount `/data`;
- PostgreSQL data path `/data/postgres`;
- state path `/data/state`;
- settings path `/data/state/settings.json`;
- snapshot state file `/data/state/snapshot-version`;
- settings schema version 1;
- existing `ICVDB_*` and `DB_*` environment variables;
- `/api` Torznab endpoint;
- `/webapi` WebUI API;
- snapshot repository `xbit18/icvdb-snapshots`.

Backward compatibility with existing volumes and installations is important.

Do not rename or remove compatibility identifiers as part of unrelated cleanup or branding changes.

## Torznab API

The main Torznab endpoint is:

```text
/api
```

Supported operations include:

- `t=caps`
- `t=search`
- `t=movie`
- `t=tvsearch`

Important categories include:

- `2000` — Movies
- `5000` — TV
- `5070` — TV / Anime

When modifying the API:

- preserve Torznab compatibility;
- prioritize compatibility with Prowlarr;
- keep `/api?t=caps` synchronized with implemented behavior;
- preserve existing parameters unless a breaking change is explicitly intended;
- do not advertise unsupported capabilities.

Torznab XML must be generated using `xml.etree.ElementTree`.

Do not manually concatenate untrusted values into XML strings.

## Database rules

Treat the ICVDB schema as an external data model.

Prefer read-only queries.

Do not modify the upstream schema or introduce application-specific database migrations unless explicitly required.

All HTTP-derived SQL values must use psycopg parameter binding.

Never build SQL by concatenating untrusted request values.

PostgreSQL should remain bound to the container loopback interface unless there is a concrete reason to change that boundary.

## Snapshot updater

Violarr automatically manages ICVDB snapshots.

The updater:

1. checks the configured GitHub release source;
2. discovers the current `.dump` asset;
3. verifies its SHA256 digest;
4. validates the dump with `pg_restore --list`;
5. restores it into a candidate database;
6. validates the candidate;
7. switches databases;
8. validates the new active database;
9. rolls back when required;
10. records the installed snapshot version.

The active database should remain available during download and restore.

Maintenance mode should be limited to the database switch and final validation.

Do not replace or destroy the active database before the candidate has been validated.

Do not remove `/data` or the application volume during ordinary upgrades.

## Settings

Persistent settings live in:

```text
/data/state/settings.json
```

Effective configuration precedence is:

```text
built-in defaults < persisted settings < runtime environment
```

Environment variables are overrides, not automatically persisted WebUI values.

Secrets such as Prowlarr API keys must never be returned by public settings endpoints.

Do not log, expose, or commit secrets.

## Result processing

Violarr supports result-processing presets and custom filtering/ranking rules.

The processing pipeline may:

- exclude results;
- score results;
- reorder results.

It affects only the results returned by Violarr.

It cannot guarantee how Prowlarr, Radarr, Sonarr, or another downstream application ultimately chooses a release.

When modifying result processing:

- preserve stable ordering for equal scores;
- keep rules bounded and deterministic;
- do not introduce arbitrary scripts or executable expressions;
- maintain predictable pagination behavior.

## Prowlarr integration

Violarr can configure itself as a Generic Torznab indexer in Prowlarr.

The integration:

- authenticates with `X-Api-Key`;
- reads Prowlarr's Generic Torznab schema;
- creates a Violarr resource from that schema;
- uses the configured app profile;
- tests the resource before creation;
- detects an already configured equivalent indexer;
- avoids duplicating equivalent indexers.

Do not hard-code Prowlarr schema defaults when they can be derived from the current Prowlarr schema response.

Remember that `localhost` inside the Violarr container refers to the container itself, not the Docker host.

## Security

Treat all HTTP input as untrusted.

Never expose:

- passwords;
- API keys;
- tokens;
- private machine paths;
- stack traces containing secrets;
- internal credentials.

The WebUI, WebAPI, and Torznab API currently do not provide their own authentication.

Deployment on port `8000` should therefore be limited to a trusted network or placed behind an authenticated reverse proxy.

Stored settings are not encrypted, so access to the `/data` volume must be protected.

## Local development

Python development uses Python 3.12.

Recommended setup on Windows:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-dev.txt
```

Frontend dependencies:

```bash
npm --prefix frontend ci
```

Documentation dependencies:

```bash
npm --prefix docs ci
```

Root Node dependencies are used for Commitlint:

```bash
npm ci
```

## Git hooks

Versioned hooks live in:

```text
.githooks/
```

Enable them locally with:

```bash
git config core.hooksPath .githooks
```

The pre-commit hook automatically:

- runs Ruff fixes and formatting on staged Python files;
- runs ESLint fixes on staged frontend source files;
- runs Prettier on staged frontend files;
- runs Prettier on staged documentation files;
- re-stages modified files.

The commit-msg hook validates commit messages with Commitlint.

A fresh clone does **not** automatically enable `core.hooksPath`; the command above must be run once.

## Commit convention

Use Conventional Commits.

Examples:

```text
feat: add result ranking preset
fix: correct Prowlarr app profile handling
docs: update installation guide
test: cover snapshot rollback
refactor: simplify settings normalization
ci: update release workflow
chore: update tooling
```

Important release semantics:

- `fix:` → patch release;
- `feat:` → minor release;
- breaking changes → major release.

Use Conventional Commit titles when squash-merging feature/fix PRs.

Merge commits such as `Merge pull request ...` may appear in history; Release Please ignores commits it cannot parse.

## Branch and release workflow

Normal development flow:

```text
feature/fix branch
        ↓
develop
        ↓
develop → main
        ↓
Release Please
        ↓
Release PR
        ↓
GitHub Release
        ↓
multi-arch Docker image on GHCR
```

Feature and fix work should normally branch from `develop` and merge back into `develop`.

`main` represents released or release-ready code.

Release Please runs on `main`.

Do not manually edit the version during normal development unless a specific release override is required.

The current version is tracked through:

- `VERSION`;
- `.release-please-manifest.json`;
- Release Please.

When Release Please creates a GitHub Release, the reusable Docker publication workflow publishes:

- the full semantic version;
- the major/minor tag;
- `latest`.

The image is built for:

```text
linux/amd64
linux/arm64
```

### Merge rules

- Feature/fix branches target `develop` and use **Squash and merge**.
- `develop` → `main` uses **Create a merge commit**.
- Do not squash `develop` → `main`, so Release Please can inspect the individual Conventional Commits.
- After each release, sync `main` back into `develop`.
- If only Docker publishing fails, fix the workflow and re-run `Publish Docker image` for the existing tag. Do not create a new release.
- Do not manually edit `VERSION`, `.release-please-manifest.json`, or `CHANGELOG.md` during normal development.

## Validation before finishing a change

Run the checks relevant to the files changed.

### Backend

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

### Frontend

```bash
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run typecheck
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

### Documentation

```bash
npm --prefix docs run format:check
npm --prefix docs run docs:build
```

### Docker

For changes affecting the image or runtime:

```bash
docker build .
```

When practical, also verify:

```bash
curl 'http://localhost:8000/api?t=caps'
```

and at least one real database-backed search:

```bash
curl -s 'http://localhost:8000/api?t=search&q=avatar'
```

Do not treat `/api?t=caps` alone as proof that PostgreSQL is working.

## CI

GitHub Actions validates pushes and pull requests for `main` and `develop`.

The CI pipeline checks:

### Backend

- Ruff lint
- Ruff formatting
- pytest

### Frontend

- ESLint
- Prettier
- TypeScript
- Vitest
- production build

### Documentation

- Prettier
- VitePress build

### Docker

- production image build

Do not weaken CI checks simply to make a failing change pass.

Fix the underlying code, tests, formatting, or configuration instead.

## Documentation rules

Update documentation when behavior changes.

Use:

- `README.md` / `README.en.md` for top-level user-facing behavior;
- `docs/` for detailed installation and usage documentation;
- `ARCHITECTURE.md` for runtime architecture, security boundaries, compatibility contracts, snapshot behavior, and protocol details.

Keep documentation aligned with actual implementation.

Do not document planned behavior as if it already exists.

## General implementation principles

Prefer:

- explicit behavior;
- small focused functions;
- minimal dependencies;
- deterministic processing;
- centralized normalization;
- parameterized SQL;
- atomic persistent writes;
- backward compatibility.

Avoid:

- unnecessary abstraction;
- speculative frameworks;
- duplicated logic;
- hidden side effects;
- unrelated refactors inside bug fixes;
- changing established compatibility identifiers without a migration plan.

When fixing a bug, prefer the smallest change that solves the underlying problem and add or update tests covering it.

## Before finishing

Confirm that:

1. relevant automated tests pass;
2. formatting and linting pass;
3. frontend type checking passes when applicable;
4. the Docker image still builds when runtime code changes;
5. no secrets or local-only configuration were committed;
6. no database dump was accidentally committed;
7. existing `/data` volumes remain compatible unless a breaking migration was explicitly intended;
8. Torznab capabilities match the implementation;
9. user-facing documentation reflects user-visible changes;
10. architecture documentation reflects architectural changes.
