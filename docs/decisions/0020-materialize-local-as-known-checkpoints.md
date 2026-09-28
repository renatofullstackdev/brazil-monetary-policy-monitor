# ADR 0020 — Materialize local `as_known` checkpoints without backdating unavailable vintages

## Status

Accepted in Sprint 13.

## Context

The database has preserved observation revisions and `available_at` since Sprint 1, but the browser previously consumed only `latest_revision` contracts. A historical view must not answer "what was known then?" by looking at the economic reference date alone: a value for 2024 that was first observed by this monitor in 2026 was not defensibly available to this system in 2024.

Some providers expose richer real-time histories than others. In particular, the authenticated FRED/ALFRED API exposes vintage dates and real-time periods, but the V1 US collector intentionally uses the keyless CSV transport. Adding a secret solely for Sprint 13 would change the operational contract and still would not solve equivalent gaps for every Brazilian source.

## Decision

1. `available_at` remains the hard knowledge boundary for `as_known`.
2. Every publisher used by the browser accepts `latest_revision` or `as_known` plus a cutoff.
3. The static browser does not query SQLite. `publish-vintages` materializes self-contained bundles under `web/data/vintages/YYYY-MM-DD/` and an index.
4. The default archive stores the first local knowledge date, the last known date in each month, and today. Exact dates can be materialized explicitly with `--date`.
5. If a source lacks authoritative historical publication/revision timestamps, a backfill becomes available only when the monitor first sees it. We do not infer availability from `reference_period`.
6. Provider-native vintage ingestion may be added later where it has a defensible operational contract. Until then, the UI labels the archive as local/defensible rather than complete real-time history.

## Consequences

- Historical reconstructions cannot look ahead to later revisions.
- Early cutoffs can legitimately show an indicator as unavailable even when its economic reference period is old.
- Static deployment is preserved: switching vintage loads another published JSON bundle, not a backend API.
- Archive growth is bounded by monthly checkpoints unless an operator explicitly materializes additional dates.
