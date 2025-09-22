CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS embeddings (
  id BIGSERIAL PRIMARY KEY,
  chunk_id BIGINT REFERENCES chunks(id) ON DELETE CASCADE,
  embedding vector(1536)
);

CREATE INDEX IF NOT EXISTS embeddings_idx
  ON embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
