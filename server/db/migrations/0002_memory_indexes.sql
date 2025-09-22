CREATE INDEX IF NOT EXISTS events_ts_idx ON events (ts DESC);
CREATE INDEX IF NOT EXISTS events_links_gin ON events USING GIN (links);
CREATE INDEX IF NOT EXISTS chunks_ts_idx ON chunks (ts DESC);
CREATE INDEX IF NOT EXISTS chunks_fts_idx ON chunks USING GIN (to_tsvector('english', text));
