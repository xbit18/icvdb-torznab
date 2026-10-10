# Diagnose a missing release

**Diagnostics** in the WebUI shows what happens inside Violarr: parameters,
local snapshot lookup, filtering/ranking and Torznab response generation. It
does not change the search or check whether downstream clients accept releases.

## Run a search

1. Open **Diagnostics → Search**, the default view.
2. Choose generic, movie or TV search and enter the query.
3. Expand **Advanced parameters** for IMDb, TMDb (movies only), season/episode
   (TV only), categories, limit and offset. Limit: 1–200; offset: 0–1000000.
   Categories are accepted but do not filter current queries. Diagnostics
   preserves that behavior without widening searches or disabling filters.
4. Select **Run diagnostics** and check the four stage statuses.
5. Inspect candidates, exclusion reasons, scores/rule indices and subtitle
   correction. **Parameters, settings and windows** lets you compare original
   and normalized input, effective preset/rules and database windows.

Rule indices are zero-based and refer to the rules in the report's settings. The
XML language of a returned release is distinct from the effect of subtitle
correction during processing.

## Interpret the result

| Observation                      | Meaning                                                                                                        |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| No candidates                    | No releases retrieved from the inspected local snapshot windows; not proof of absence from the entire database |
| Excluded by filtering            | A preset or rule excluded this candidate; inspect its reason and effective settings                            |
| Outside final page               | The candidate was retained but not selected for this page                                                      |
| Selected, not confirmed returned | Selection for XML does not prove serialization and validation succeeded                                        |
| Returned in validated XML        | Violarr generated the release in its output; Prowlarr/Sonarr/Radarr acceptance needs separate investigation    |
| Failed / not-run stage           | The pipeline is partial; inspect errors rather than interpreting HTTP 200 as success                           |

Counts are not whole-database totals. Processed presets use 1000-row windows,
window-local ranking and pages without backfilling from later windows.
Uninspected releases may exist elsewhere. Violarr uses a **local ICVDB
snapshot**, which may differ from newer content or live search paths used by the
Stremio addon. It does not scrape or compare live Stremio results.

If the database is unavailable or being switched, wait and retry. Stage errors
retain only observed information; an HTTP error may produce no report at all.

## Observe client requests

1. Open **Requests** and enable **Monitor incoming searches**.
2. Run a search from your client through Prowlarr.
3. Select **Refresh**, or wait for the five-second refresh while this view is
   open.
4. Select **Inspect request** for original/normalized parameters, strategy,
   counts, duration, HTTP status, stages and errors.
5. Select **Replay request** for a **fresh diagnostic search** with the original
   parameters. Current database/settings may differ from historical conditions.
   Replay is not added to request history.

Monitoring is disabled by default. It retains at most 100 recent Torznab `/api`
requests in memory, not release sets; oldest entries are discarded. Disabling
capture stops new entries but preserves history; **Clear history** removes it.
Restarting Violarr resets both state and history. Redacted, truncated or invalid
requests cannot be replayed.

## Share a report safely

1. After a search, select **Export report**.
2. Read **Report preview**: it is the JSON that will be downloaded, with report
   version `1`, application/snapshot versions, sanitized parameters, settings,
   stages, windows, counts, candidate details and safe errors.
3. Select **Download JSON**, then remove private data before attaching it to an
   issue. Download is local and sends nothing to external services.

Export excludes credentials, headers, complete magnets, SQL and internal
configuration, bounds details/text and refuses reports over 4 MB. Structural
redaction **does not anonymize** titles, queries or rule values. Reports may be
partial when errors or truncation are indicated; export is disabled without a
report.

::: warning Trusted network and privacy

WebUI, WebAPI and Torznab have no authentication. Anyone who can reach Violarr
can execute diagnostics, enable monitoring, and read or clear history. Expose
port 8000 only on a trusted network or behind an authenticated proxy. Disable
monitoring and clear history when you finish.

:::
