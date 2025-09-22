CREATE TABLE IF NOT EXISTS entities (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  name TEXT,
  meta JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS attributes (
  entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
  key TEXT,
  value JSONB,
  valid_from TIMESTAMPTZ,
  valid_to   TIMESTAMPTZ,
  PRIMARY KEY (entity_id, key, valid_from)
);

CREATE TABLE IF NOT EXISTS relations (
  src_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
  rel TEXT,
  dst_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
  weight REAL DEFAULT 1.0,
  valid_from TIMESTAMPTZ,
  valid_to   TIMESTAMPTZ,
  PRIMARY KEY (src_id, rel, dst_id, valid_from)
);

CREATE TABLE IF NOT EXISTS events (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL,
  actor_id TEXT REFERENCES entities(id),
  type TEXT,
  payload JSONB,
  links TEXT[]
);

CREATE TABLE IF NOT EXISTS daily_state (
  date DATE PRIMARY KEY,
  global_state JSONB,
  summary TEXT
);

CREATE TABLE IF NOT EXISTS entity_state (
  date DATE,
  entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
  state JSONB,
  summary TEXT,
  PRIMARY KEY (date, entity_id)
);

CREATE TABLE IF NOT EXISTS chunks (
  id BIGSERIAL PRIMARY KEY,
  ref_type TEXT,
  ref_id TEXT,
  ts TIMESTAMPTZ,
  text TEXT,
  meta JSONB
);
