from __future__ import annotations

from pathlib import Path
from typing import Dict

import pytest

from server.src.memory.config import MemoryConfig, create_engine_from_config, load_memory_config
from server.src.memory.store import MemoryStore


@pytest.fixture()
def memory_env(tmp_path: Path) -> Dict[str, str]:
    db_path = tmp_path / "memory.db"
    return {
        "MEMORY_ENABLED": "true",
        "MEMORY_DB_VENDOR": "sqlite",
        "MEMORY_DB_URL": f"sqlite:///{db_path}",
        "VECTOR_DIM": "64",
    }


@pytest.fixture()
def memory_config(memory_env: Dict[str, str]) -> MemoryConfig:
    return load_memory_config(memory_env)


@pytest.fixture()
def memory_store(memory_config: MemoryConfig) -> MemoryStore:
    engine = create_engine_from_config(memory_config)
    store = MemoryStore(engine, memory_config)
    store.ensure_schema()
    return store
