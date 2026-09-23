CREATE TABLE yield_curve_quotes (
    id INTEGER PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    instrument_type TEXT NOT NULL CHECK (length(trim(instrument_type)) > 0),
    maturity_date TEXT NOT NULL,
    reference_date TEXT NOT NULL,
    buy_yield REAL,
    sell_yield REAL,
    buy_price REAL,
    sell_price REAL,
    base_price REAL,
    available_at TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    vintage_key TEXT NOT NULL CHECK (length(trim(vintage_key)) > 0),
    ingestion_run_id INTEGER REFERENCES ingestion_runs(id) ON DELETE SET NULL,
    quality_flags_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (reference_date < maturity_date),
    CHECK (available_at <= first_seen_at),
    CHECK (first_seen_at <= last_seen_at),
    UNIQUE (source_id, instrument_type, maturity_date, reference_date, vintage_key)
);

CREATE INDEX idx_yield_curve_quotes_reference
    ON yield_curve_quotes(source_id, reference_date, maturity_date);
CREATE INDEX idx_yield_curve_quotes_latest
    ON yield_curve_quotes(source_id, instrument_type, maturity_date, reference_date, available_at);
