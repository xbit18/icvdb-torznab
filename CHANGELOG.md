# Changelog

All notable changes to this project are documented here.

## [1.1.4](https://github.com/xbit18/violarr/compare/v1.1.3...v1.1.4) (2026-10-07)


### Bug Fixes

* improve Prowlarr connection diagnostics ([3dbfeea](https://github.com/xbit18/violarr/commit/3dbfeea27b94af4a78d023f0644addbaa15062b2))

## [1.1.3](https://github.com/xbit18/violarr/compare/v1.1.2...v1.1.3) (2026-10-06)


### Bug Fixes

* apply database update settings from WebUI ([d2403a0](https://github.com/xbit18/violarr/commit/d2403a0505f7539c0ee25e1d6a73ea31ea0496d6))

## v1.1.2 - 2026-10-05
### Added
- support for arm64 image

## v1.1.1 — 2026-10-05

### Solved
 - too small payload limiter for Prowlarr
 - bug in flow for adding Violarr as Prowlarr indexer

## v1.1.0 — 2026-10-05

### Added

- Rebranded the public product, repository metadata, package metadata, and
  primary container image as Violarr.
- Persistent schema-v1 settings at `/data/state/settings.json`, including atomic
  writes, environment precedence, validation, and masked Prowlarr secrets.
- Result-processing presets for unfiltered, Italian-preferred, Italian-only, and
  bounded custom score/exclusion rules.
- Same-origin `/webapi` endpoints for status, settings, result processing, and
  schema-derived Prowlarr test/install operations.
- Vue WebUI served from `/` with responsive light/dark styling.
- Multi-stage frontend build for the existing single-container runtime.
- Markdown-first VitePress documentation and GitHub Pages deployment workflow.

### Compatibility

- Publishes the Violarr image at `ghcr.io/xbit18/violarr`.
- Keeps the Compose service/container alias `icvdb-torznab`, named volume
  `icvdb_torznab_data`, `/data` paths, schema version 1, `ICVDB_*` and `DB_*`
  environment variables, `/api` and `/webapi`, and snapshot repository
  `xbit18/icvdb-snapshots` unchanged.
- Preserves the v1.0 `/api` Torznab operations, parameters, categories,
  pagination defaults, and XML mapping.
- Preserves PostgreSQL 16, port `8000`, the single `/data` volume, snapshot
  source, state file, candidate validation, maintenance-only switch, and rollback.
- Existing v1.0 volumes are expected to be reused; v1.1 adds the settings file
  without replacing PostgreSQL or snapshot state.

### Security

- The WebUI, WebAPI, and Torznab endpoint remain unauthenticated and should be
  restricted to a trusted LAN or protected by an authenticated reverse proxy.
- Prowlarr API keys are omitted from normal read responses and sanitized from
  high-level errors.

## v1.0

- Introduced the single-container PostgreSQL 16 and FastAPI Torznab service.
- Added automatic GitHub snapshot bootstrap and periodic safe updates.
- Established `/api` support for capabilities, generic, movie, and TV searches.
