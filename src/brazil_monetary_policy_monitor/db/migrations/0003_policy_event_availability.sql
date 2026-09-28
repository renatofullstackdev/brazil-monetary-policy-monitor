ALTER TABLE events ADD COLUMN available_at TEXT;
ALTER TABLE events ADD COLUMN retrieved_at TEXT;
ALTER TABLE events ADD COLUMN last_seen_at TEXT;
ALTER TABLE events ADD COLUMN content_hash TEXT;

UPDATE events
SET available_at = COALESCE(published_at, created_at, occurred_at),
    retrieved_at = COALESCE(created_at, published_at, occurred_at),
    last_seen_at = COALESCE(created_at, published_at, occurred_at),
    content_hash = event_key
WHERE available_at IS NULL;

CREATE TABLE event_revisions (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    occurred_at TEXT NOT NULL,
    published_at TEXT,
    url TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    available_at TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    content_hash TEXT NOT NULL CHECK (length(trim(content_hash)) > 0),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK (available_at <= retrieved_at),
    CHECK (retrieved_at <= last_seen_at),
    UNIQUE(event_id, content_hash)
);

INSERT INTO event_revisions(
    event_id, title, occurred_at, published_at, url, metadata_json,
    available_at, retrieved_at, last_seen_at, content_hash
)
SELECT
    id, title, occurred_at, published_at, url, metadata_json,
    available_at, retrieved_at, last_seen_at, content_hash
FROM events;

CREATE INDEX idx_events_as_known ON events(available_at, event_type, occurred_at);
CREATE INDEX idx_events_meeting_number ON events(source_event_id, event_type);
CREATE INDEX idx_event_revisions_as_known ON event_revisions(event_id, available_at, id);
CREATE INDEX idx_event_revisions_available ON event_revisions(available_at);
