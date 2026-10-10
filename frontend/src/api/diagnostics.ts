import { requestJson } from './client'

export type SearchType = 'search' | 'movie' | 'tvsearch'
export interface SearchInput {
  t: SearchType
  q?: string | null
  imdbid?: string | null
  tmdbid?: number | null
  season?: number | null
  ep?: number | null
  cat?: string | null
  limit?: number
  offset?: number
}
export type Parameters = Record<string, string | number | null>
export type StageName = 'input' | 'database' | 'processing' | 'serialization'
export interface Stage {
  status: 'not_run' | 'running' | 'success' | 'failed'
  duration_ms: number
}
export interface Counts {
  candidates: number
  excluded: number
  retained: number
  outside_page: number
  selected: number
  returned: number
}
export interface SafeError {
  stage: StageName | 'http'
  code: string
  message: string
}
export interface Release {
  id: string
  title: string | null
  size: number | null
  seeders: number | null
  provider: string | null
  type: string | null
  category: number
  language: string | null
  subtitle_corrected_for_processing: boolean
  status: 'excluded' | 'outside_page' | 'selected' | 'returned'
  reason: string | null
  score: number
  score_rules: number[]
}
export interface Processing {
  preset: 'unfiltered' | 'italian_only' | 'italian_preferred' | 'custom'
  subtitle_language_correction: boolean
  custom_rule_count: number
  custom_rules: {
    index: number
    enabled: boolean
    field: string
    operator: string
    value: string | number
    action: string
    score: number | null
  }[]
}
export interface Observation {
  original: Parameters
  normalized: Parameters
  strategy: string | null
  stages: Record<StageName, Stage>
  counts: Counts
  errors: SafeError[]
  duration_ms: number
  truncated: boolean
  replayable: boolean
}
export interface SearchReport extends Observation {
  report_version: 1
  application_version: string
  snapshot_version: string | null
  generated_at: string
  windows: { offset: number; limit: number; candidates: number }[]
  processing: Processing | null
  serialization_settings: { subtitle_language_correction: boolean } | null
  releases: Release[]
  limitations: string[]
}
export interface MonitoredRequest extends Observation {
  id: number
  timestamp: string
  status_code: number
}
export interface MonitoringStatus {
  enabled: boolean
  capacity: number
  count: number
}
const root = '/webapi/diagnostics'
export const diagnosticsApi = {
  search: (value: SearchInput, signal?: AbortSignal) =>
    requestJson<SearchReport>(
      `${root}/search`,
      { method: 'POST', body: JSON.stringify(value), signal },
      100_000,
    ),
  monitoring: (signal?: AbortSignal) =>
    requestJson<MonitoringStatus>(`${root}/monitoring`, { signal }),
  configure: (enabled: boolean, signal?: AbortSignal) =>
    requestJson<MonitoringStatus>(`${root}/monitoring`, {
      method: 'PUT',
      body: JSON.stringify({ enabled }),
      signal,
    }),
  requests: (signal?: AbortSignal) =>
    requestJson<{ requests: MonitoredRequest[] }>(`${root}/requests`, { signal }),
  clear: (signal?: AbortSignal) =>
    requestJson<{ requests: MonitoredRequest[] }>(`${root}/requests`, { method: 'DELETE', signal }),
}

// Project every level of the versioned contract. Never serialize arbitrary response fields.
function pick(value: unknown, keys: readonly string[]): Record<string, unknown> {
  const object = value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
  return Object.fromEntries(keys.filter((key) => key in object).map((key) => [key, object[key]]))
}
function safe(value: unknown): unknown {
  if (typeof value === 'string')
    return value
      .replace(/(?:magnet:\?|[a-z][a-z0-9+.-]*:\/\/)\S*/gi, '[redacted]')
      .replace(/(?:\/|[A-Z]:\\)[^\s]+/g, '[redacted]')
      .replace(/(?:password|apikey|api_key|token)\s*[:=]\s*\S+/gi, '[redacted]')
      .split('')
      .filter((character) => character.charCodeAt(0) >= 32 && character.charCodeAt(0) !== 127)
      .join('')
      .slice(0, 512)
  if (Array.isArray(value)) return value.map(safe)
  if (value && typeof value === 'object')
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, safe(item)]))
  return typeof value === 'number' && !Number.isFinite(value) ? null : value
}
export function exportReport(report: SearchReport): string {
  if (report.report_version !== 1) throw new Error('Unsupported report version')
  const parameters = ['t', 'q', 'imdbid', 'tmdbid', 'season', 'ep', 'cat', 'limit', 'offset']
  const projected = {
    ...pick(report, [
      'report_version',
      'application_version',
      'snapshot_version',
      'generated_at',
      'strategy',
      'duration_ms',
      'truncated',
      'replayable',
    ]),
    original: pick(report.original, parameters),
    normalized: pick(report.normalized, parameters),
    stages: Object.fromEntries(
      (['input', 'database', 'processing', 'serialization'] as const).map((name) => [
        name,
        pick(report.stages[name], ['status', 'duration_ms']),
      ]),
    ),
    counts: pick(report.counts, [
      'candidates',
      'excluded',
      'retained',
      'outside_page',
      'selected',
      'returned',
    ]),
    windows: report.windows
      .slice(0, 2)
      .map((window) => pick(window, ['offset', 'limit', 'candidates'])),
    processing: report.processing
      ? {
          ...pick(report.processing, [
            'preset',
            'subtitle_language_correction',
            'custom_rule_count',
          ]),
          custom_rules: report.processing.custom_rules
            .slice(0, 100)
            .map((rule) =>
              pick(rule, ['index', 'enabled', 'field', 'operator', 'value', 'action', 'score']),
            ),
        }
      : null,
    serialization_settings: report.serialization_settings
      ? pick(report.serialization_settings, ['subtitle_language_correction'])
      : null,
    releases: report.releases.slice(0, 2000).map((release) => ({
      ...pick(release, [
        'id',
        'title',
        'size',
        'seeders',
        'provider',
        'type',
        'category',
        'language',
        'subtitle_corrected_for_processing',
        'status',
        'reason',
        'score',
      ]),
      score_rules: release.score_rules.slice(0, 100),
    })),
    errors: report.errors.slice(0, 4).map((error) => pick(error, ['stage', 'code', 'message'])),
    limitations: report.limitations.slice(0, 8),
  }
  const serialized = JSON.stringify(safe(projected), null, 2)
  if (new Blob([serialized]).size > 4_000_000) throw new Error('Report exceeds export limit')
  return serialized
}

export function exportHistory(requests: MonitoredRequest[]): string {
  if (!Array.isArray(requests) || requests.length > 100) throw new Error('Invalid request history')
  // Every leaf is scalar: unexpected nested objects must not bypass the allowlist.
  const scalars = (value: unknown, keys: readonly string[]) =>
    Object.fromEntries(
      Object.entries(pick(value, keys)).filter(
        ([, item]) => item === null || ['string', 'number', 'boolean'].includes(typeof item),
      ),
    )
  const parameters = ['t', 'q', 'imdbid', 'tmdbid', 'season', 'ep', 'cat', 'limit', 'offset']
  const projected = {
    export_version: 1,
    kind: 'monitored_requests',
    generated_at: new Date().toISOString(),
    requests: requests.map((entry) => ({
      ...scalars(entry, [
        'id',
        'timestamp',
        'status_code',
        'strategy',
        'duration_ms',
        'truncated',
        'replayable',
      ]),
      original: scalars(entry.original, parameters),
      normalized: scalars(entry.normalized, parameters),
      stages: Object.fromEntries(
        (['input', 'database', 'processing', 'serialization'] as const).map((name) => [
          name,
          scalars(entry.stages[name], ['status', 'duration_ms']),
        ]),
      ),
      counts: scalars(entry.counts, [
        'candidates',
        'excluded',
        'retained',
        'outside_page',
        'selected',
        'returned',
      ]),
      errors: entry.errors.map((error) => scalars(error, ['stage', 'code', 'message'])),
    })),
  }
  const serialized = JSON.stringify(safe(projected), null, 2)
  if (new Blob([serialized]).size > 4_000_000) throw new Error('History exceeds export limit')
  return serialized
}
