# ADR 0019 — Use a canonical US Taylor benchmark and keyless FRED transport

## Status
Accepted in Sprint 12.

## Decision
US observed benchmark series are retrieved from the Federal Reserve Bank of St. Louis FRED graph-CSV endpoint, which does not require an API key. Each response is snapshotted before parsing and the originating FRED series ID remains in metadata.

The US Taylor benchmark uses the canonical assumptions `r*=2%`, inflation target `2%`, `alpha=0.5`, and `beta=0.5`. Inflation is realized 12-month PCE and the output gap is derived from BEA real GDP relative to CBO real potential GDP.

The canonical `r*=2%` is a model assumption, not a claim about the current neutral rate. The New York Fed's LW/HLW r-star estimates remain a documented complementary source but are not silently substituted into the Taylor benchmark.

## Why
This keeps the benchmark reproducible, dependency-free and transparent while avoiding false precision around an unobserved, model-dependent neutral rate. It also avoids requiring FRED API credentials for a static scheduled pipeline.

## Consequences
Historical US derived series use the latest revisions stored by the monitor unless a future vintage pipeline is added. The Taylor benchmark must always disclose that limitation and must not be presented as the FOMC reaction function or a policy recommendation.
