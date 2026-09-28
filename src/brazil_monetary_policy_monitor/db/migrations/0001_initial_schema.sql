CREATE TABLE sources (
    id INTEGER PRIMARY KEY,
    key TEXT NOT NULL UNIQUE CHECK (length(trim(key)) > 0),
    provider TEXT NOT NULL CHECK (length(trim(provider)) > 0),
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    url TEXT,
    documentation_url TEXT,
    license TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE ingestion_runs (
    id INTEGER PRIMARY KEY,
    provider TEXT NOT NULL CHECK (length(trim(provider)) > 0),
    source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed', 'partial')),
    records_received INTEGER NOT NULL DEFAULT 0 CHECK (records_received >= 0),
    records_inserted INTEGER NOT NULL DEFAULT 0 CHECK (records_inserted >= 0),
    records_updated INTEGER NOT NULL DEFAULT 0 CHECK (records_updated >= 0),
    records_unchanged INTEGER NOT NULL DEFAULT 0 CHECK (records_unchanged >= 0),
    error_json TEXT,
    collector_version TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (finished_at IS NULL OR started_at <= finished_at),
    CHECK (
        (status = 'running' AND finished_at IS NULL)
        OR
        (status <> 'running' AND finished_at IS NOT NULL)
    )
);

CREATE TABLE series (
    id INTEGER PRIMARY KEY,
    key TEXT NOT NULL UNIQUE CHECK (length(trim(key)) > 0),
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    source_series_id TEXT,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    description TEXT,
    unit_original TEXT,
    unit_normalized TEXT NOT NULL CHECK (length(trim(unit_normalized)) > 0),
    frequency TEXT NOT NULL CHECK (length(trim(frequency)) > 0),
    data_kind TEXT NOT NULL CHECK (
        data_kind IN ('observed', 'survey', 'estimated', 'derived')
    ),
    transformation TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (
        status IN ('active', 'inactive', 'retired')
    ),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX idx_series_source ON series(source_id);

CREATE TABLE observations (
    id INTEGER PRIMARY KEY,
    series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE RESTRICT,
    reference_period TEXT NOT NULL CHECK (length(trim(reference_period)) > 0),
    reference_start TEXT NOT NULL,
    reference_end TEXT NOT NULL,
    value REAL NOT NULL,
    published_at TEXT,
    available_at TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    vintage_key TEXT NOT NULL CHECK (length(trim(vintage_key)) > 0),
    source_revision TEXT,
    ingestion_run_id INTEGER REFERENCES ingestion_runs(id) ON DELETE SET NULL,
    quality_flags_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (reference_start <= reference_end),
    CHECK (published_at IS NULL OR published_at <= available_at),
    CHECK (available_at <= first_seen_at),
    CHECK (first_seen_at <= last_seen_at),
    UNIQUE (series_id, reference_period, vintage_key)
);

CREATE INDEX idx_observations_series_period
    ON observations(series_id, reference_start, reference_end);
CREATE INDEX idx_observations_as_known
    ON observations(series_id, available_at, reference_period);

CREATE TABLE parameters (
    id INTEGER PRIMARY KEY,
    key TEXT NOT NULL CHECK (length(trim(key)) > 0),
    value REAL NOT NULL,
    unit TEXT NOT NULL CHECK (length(trim(unit)) > 0),
    data_kind TEXT NOT NULL CHECK (
        data_kind IN ('observed', 'survey', 'estimated', 'derived')
    ),
    effective_from TEXT NOT NULL,
    effective_to TEXT,
    published_at TEXT,
    available_at TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    version_key TEXT NOT NULL CHECK (length(trim(version_key)) > 0),
    source_id INTEGER REFERENCES sources(id) ON DELETE RESTRICT,
    source_reference TEXT,
    methodology TEXT,
    ingestion_run_id INTEGER REFERENCES ingestion_runs(id) ON DELETE SET NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (effective_to IS NULL OR effective_from <= effective_to),
    CHECK (published_at IS NULL OR published_at <= available_at),
    CHECK (available_at <= retrieved_at),
    UNIQUE (key, effective_from, version_key)
);

CREATE INDEX idx_parameters_key_effective
    ON parameters(key, effective_from, effective_to);
CREATE INDEX idx_parameters_as_known
    ON parameters(key, available_at);

CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    event_key TEXT NOT NULL UNIQUE CHECK (length(trim(event_key)) > 0),
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    event_type TEXT NOT NULL CHECK (length(trim(event_type)) > 0),
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    occurred_at TEXT NOT NULL,
    published_at TEXT,
    url TEXT,
    source_event_id TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX idx_events_occurred_at ON events(occurred_at);
CREATE INDEX idx_events_type_occurred ON events(event_type, occurred_at);
