CREATE TABLE IF NOT EXISTS entities (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  name TEXT,
  meta TEXT DEFAULT '{}' CHECK (json_valid(meta)),
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS attributes (
  entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
  key TEXT,
  value TEXT CHECK (value IS NULL OR json_valid(value)),
  valid_from TEXT,
  valid_to   TEXT,
  PRIMARY KEY (entity_id, key, valid_from)
);

CREATE TABLE IF NOT EXISTS relations (
  src_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
  rel TEXT,
  dst_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
  weight REAL DEFAULT 1.0,
  valid_from TEXT,
  valid_to   TEXT,
  PRIMARY KEY (src_id, rel, dst_id, valid_from)
);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  actor_id TEXT REFERENCES entities(id),
  type TEXT,
  payload TEXT CHECK (payload IS NULL OR json_valid(payload)),
  links TEXT
);

CREATE TABLE IF NOT EXISTS daily_state (
  date TEXT PRIMARY KEY,
  global_state TEXT CHECK (global_state IS NULL OR json_valid(global_state)),
  summary TEXT
);

CREATE TABLE IF NOT EXISTS entity_state (
  date TEXT,
  entity_id TEXT REFERENCES entities(id) ON DELETE CASCADE,
  state TEXT CHECK (state IS NULL OR json_valid(state)),
  summary TEXT,
  PRIMARY KEY (date, entity_id)
);

CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ref_type TEXT,
  ref_id TEXT,
  ts TEXT,
  text TEXT,
  meta TEXT CHECK (meta IS NULL OR json_valid(meta))
);
