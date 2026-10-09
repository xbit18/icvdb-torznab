# Result processing

Choose what Prowlarr receives under **Result processing**. Start with
**Unfiltered** and change preset only when you know which results you want to
promote or hide.

- **Unfiltered** — starting choice; includes every result in its original order.
- **Italian preferred** — promotes likely Italian releases without hiding the
  alternatives.
- **Italian only** — shows only titles with explicit Italian markers.
- **Custom** — applies your [custom rules](../features/custom-filters).

Select **Save result processing** and wait for the confirmation message.

::: warning Downstream selection

Ranking ICVDB results does not guarantee that Radarr or Sonarr will select the
top ICVDB item. Their own profiles, scoring, and availability rules still apply.

:::

::: danger Hard filters hide results

**Italian only** and custom **Exclude** rules remove results before Prowlarr can
receive them.

:::

Read more about [Italian ranking](../features/italian-ranking) or the
[technical details](../how-it-works/result-processing).

## Language correction

**Correct Italian subtitle detection** is disabled by default. When enabled, it
prevents releases with explicit markers such as `SUB ITA`, `SUB.ITA`,
`SUB-ITA`, or `ITA.SUBBED` from being interpreted as Italian audio merely
because the subtitles are Italian.

This is a heuristic: for matching results, Violarr sends `language=English`
in Torznab metadata; **it does not inspect actual audio tracks**. It skips
releases with separate Italian audio indicators or `MULTI`/`DUAL` markers.
Original titles and magnet links are unchanged. Italian presets also avoid
interpreting corrected subtitle-only releases as Italian.
