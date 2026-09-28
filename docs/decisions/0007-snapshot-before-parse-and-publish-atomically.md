# ADR 0007 — Snapshot provider payloads before parsing and publish JSON atomically

## Context

The monitor depends on external official providers whose availability and schemas are outside the project's control. A successful HTTP response can still contain malformed or unexpectedly shaped content, and a publication failure must not replace a previously valid frontend artifact with a partial file.

The first real pipeline, BCB SGS series 432, is also the template for later collectors. Its failure semantics therefore need to be explicit before more providers are added.

## Decision

For provider responses that can be reasonably retained:

1. save the exact response bytes before parsing or normalization;
2. record URL, byte count and SHA-256 in a per-ingestion manifest;
3. parse the full response before writing any observations from that response;
4. persist only validated normalized records;
5. write published JSON to a temporary file in the destination directory and replace the previous artifact atomically only after serialization and flush succeed;
6. record provider or validation failures in `ingestion_runs` and the snapshot manifest without deleting previous normalized observations or published JSON.

An ingestion can therefore end as:

- `succeeded`: collection, persistence and publication completed;
- `failed`: collection/validation failed before normalized persistence;
- `partial`: normalized persistence succeeded but a later pipeline stage such as publication failed.

## Why

Raw snapshots preserve the evidence needed to diagnose parser bugs, provider schema changes and historical disagreements without relying on the upstream API to reproduce an old response.

Atomic publication ensures the static frontend sees either the previous complete artifact or the next complete artifact, never an intermediate file.

Keeping the previous valid database state and JSON on provider failure makes upstream outages observable without turning them into data loss or dashboard downtime.

## Consequences

- runtime storage grows with successful HTTP payloads and failed-but-received payloads;
- snapshots are runtime data and are ignored by Git;
- retention/archival policy can be added later without changing collector semantics;
- collectors must validate complete payloads instead of silently accepting valid-looking rows from a malformed response;
- publication code must use same-filesystem temporary files so `os.replace` remains atomic.

## Alternatives considered

### Parse first, snapshot only valid responses

Rejected because malformed responses are precisely the evidence most useful for diagnosing upstream changes.

### Write JSON directly to the final path

Rejected because interruption or serialization failure could leave a truncated artifact consumed by the static frontend.

### Delete stale data when refresh fails

Rejected because absence of a fresh upstream response is not evidence that previously validated observations became invalid.
