CREATE TABLE IF NOT EXISTS embeddings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chunk_id INTEGER REFERENCES chunks(id) ON DELETE CASCADE,
  embedding BLOB
);
CREATE INDEX IF NOT EXISTS embeddings_chunk_idx ON embeddings (chunk_id);
