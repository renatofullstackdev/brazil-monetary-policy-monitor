CREATE TABLE market_curve_points (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    curve_key TEXT NOT NULL CHECK (length(trim(curve_key)) > 0),
    reference_date TEXT NOT NULL,
    point_key TEXT NOT NULL CHECK (length(trim(point_key)) > 0),
    tenor_business_days INTEGER CHECK (tenor_business_days IS NULL OR tenor_business_days > 0),
    maturity_date TEXT,
    instrument_key TEXT,
    rate_percent REAL NOT NULL,
    price_value REAL,
    available_at TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    vintage_key TEXT NOT NULL CHECK (length(trim(vintage_key)) > 0),
    ingestion_run_id INTEGER REFERENCES ingestion_runs(id) ON DELETE SET NULL,
    quality_flags_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (maturity_date IS NULL OR reference_date <= maturity_date),
    CHECK (available_at <= first_seen_at),
    CHECK (first_seen_at <= last_seen_at),
    UNIQUE (source_id, curve_key, reference_date, point_key, vintage_key)
);

CREATE INDEX idx_market_curve_points_reference
    ON market_curve_points(source_id, curve_key, reference_date, tenor_business_days);
CREATE INDEX idx_market_curve_points_latest
    ON market_curve_points(source_id, curve_key, reference_date, point_key, available_at);
