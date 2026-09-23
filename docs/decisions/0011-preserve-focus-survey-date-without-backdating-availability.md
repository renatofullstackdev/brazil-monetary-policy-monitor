# ADR 0011 — Preserve Focus survey dates without backdating availability

## Context

The Focus OData API exposes a `Data` field identifying the date of the expectation statistic. The BCB open-data catalog states that market-expectation statistics are calculated daily and published on the first business day of each week. A historical API row therefore tells us when the statistic was calculated, but does not by itself prove the exact timestamp at which that historical row became public.

The dashboard also needs a horizon-aligned inflation input. The Copom expresses the relevant policy horizon as a quarter, while the Focus monthly endpoint exposes medians for individual reference months.

## Decision

Add `observations.source_observation_at` as a separate temporal concept. For Focus backfills:

- `source_observation_at` stores the API `Data` date;
- `published_at` remains `NULL` unless an authoritative publication timestamp is available;
- `available_at` is when this monitor first retrieved that vintage;
- `source_revision` also retains the survey/statistic date for auditability.

Represent the relevant Copom horizon with an explicit, source-backed registry instead of deriving it from a calendar rule.

Construct a horizon-aligned inflation proxy by compounding the twelve monthly Focus medians ending in the relevant quarter. Store that result as `derived`, never `survey`, because compounding monthly medians is not mathematically identical to the median of institutions' cumulative twelve-month forecasts.

## Consequences

Historical Focus data can be plotted by its source statistic date without contaminating `as_known` queries with fabricated publication timestamps.

The prospective Taylor input can match the Copom's quarter window while preserving the transformation that produced it.

Backfilled observations will initially share the monitor's retrieval-time `available_at`; `source_observation_at` provides the provider chronology used to select the latest source revision when availability timestamps tie.

## Alternatives considered

Using the Focus `Data` field as `published_at` was rejected because it would overstate what the open-data metadata proves about historical public availability.

Using annual Focus expectations directly for a quarterly policy horizon was rejected because calendar-year forecasts and four-quarter inflation ending in a specific quarter are different objects.

Using a fixed twelve-month-ahead Focus statistic was rejected as the canonical policy-horizon input because the Copom horizon can be materially longer or shorter than twelve months.
