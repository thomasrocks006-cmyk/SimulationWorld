CREATE INDEX IF NOT EXISTS events_ts_idx ON events (ts DESC);
CREATE INDEX IF NOT EXISTS events_links_idx ON events (links);
CREATE INDEX IF NOT EXISTS chunks_ts_idx ON chunks (ts DESC);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(text, content='');
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
  INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES('delete', old.id, old.text);
END;
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
  INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES('delete', old.id, old.text);
  INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
END;
