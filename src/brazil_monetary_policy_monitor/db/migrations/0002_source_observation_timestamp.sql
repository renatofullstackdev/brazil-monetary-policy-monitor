ALTER TABLE observations ADD COLUMN source_observation_at TEXT;

CREATE INDEX idx_observations_source_observation
    ON observations(series_id, reference_period, source_observation_at);
