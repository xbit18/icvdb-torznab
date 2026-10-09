import type { AppStatus, PublicSettings } from '../api/types'

export const statusFixture: AppStatus = {
  api_version: 1,
  application_version: 'test-version',
  database: { connected: true },
  updater: {
    installed_version: 'db-2026-08-21',
    latest_version: 'db-2026-09-01',
    enabled: true,
    updating: false,
    maintenance: false,
    last_check: '2026-09-01T10:00:00Z',
    next_check: '2026-09-02T10:00:00Z',
    last_error: null,
  },
  result_processing: { preset: 'italian_preferred', custom_rule_count: 2 },
  prowlarr: { configured: true, connected: true, indexer_installed: false, error: null },
}

export const settingsFixture: PublicSettings = {
  schema_version: 1,
  database_update: { enabled: true, interval_seconds: 86400 },
  result_processing: { preset: 'unfiltered', custom_rules: [], subtitle_language_correction: false },
  prowlarr: {
    url: 'http://prowlarr:9696',
    indexer_url: 'http://icvdb-torznab:8000/api',
    api_key_configured: true,
  },
}
