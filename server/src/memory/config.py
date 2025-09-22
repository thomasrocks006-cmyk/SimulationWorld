from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Optional
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


@dataclass
class RetrieverLimits:
    chunks: int = 200
    events: int = 1000
    states_days: int = 14


@dataclass
class MemoryConfig:
    enabled: bool = False
    db_url: str = "sqlite:///./memory.db"
    db_vendor: str = "sqlite"
    embeddings_model: str = "text-embedding-3-large"
    llm_model: str = "gpt-4o-mini"
    max_tokens: int = 30_000
    vector_dim: int = 1536
    retriever_limits: RetrieverLimits = field(default_factory=RetrieverLimits)
    echo_sql: bool = False
    llm_api_base: str = "https://api.openai.com/v1"
    llm_api_key: Optional[str] = None
    embeddings_api_base: str = "https://api.openai.com/v1"
    embeddings_api_key: Optional[str] = None
    http_timeout: float = 15.0

    @property
    def is_sqlite(self) -> bool:
        return self.db_vendor == "sqlite" or self.db_url.startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        return self.db_vendor == "postgres" or self.db_url.startswith("postgres")

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key and self.llm_model)

    @property
    def embeddings_enabled(self) -> bool:
        key = self.embeddings_api_key or self.llm_api_key
        return bool(key and self.embeddings_model)


def _determine_vendor(db_url: str, explicit: str | None) -> str:
    if explicit:
        return explicit.lower()
    parsed = urlparse(db_url)
    scheme = (parsed.scheme or "sqlite").lower()
    if "+" in scheme:
        scheme = scheme.split("+")[0]
    if scheme in {"postgres", "postgresql", "psql"}:
        return "postgres"
    if scheme in {"sqlite", "file"}:
        return "sqlite"
    return scheme


def load_memory_config(env: Dict[str, str] | None = None) -> MemoryConfig:
    env = env if env is not None else os.environ
    enabled_raw = env.get("MEMORY_ENABLED", "false").strip().lower()
    enabled = enabled_raw in {"1", "true", "yes", "on"}
    db_url = env.get("MEMORY_DB_URL") or ("sqlite:///./memory.db")
    vendor = _determine_vendor(db_url, env.get("MEMORY_DB_VENDOR"))
    config = MemoryConfig(
        enabled=enabled,
        db_url=db_url,
        db_vendor=vendor,
        embeddings_model=env.get("EMBEDDINGS_MODEL", "text-embedding-3-large"),
        llm_model=env.get("LLM_MODEL", "gpt-4o-mini"),
        max_tokens=int(env.get("MEMORY_MAX_TOKENS", "30000")),
        vector_dim=int(env.get("VECTOR_DIM", "1536")),
        retriever_limits=RetrieverLimits(
            chunks=int(env.get("RETRIEVER_LIMIT_CHUNKS", env.get("RETRIEVER_LIMITS_CHUNKS", "200"))),
            events=int(env.get("RETRIEVER_LIMIT_EVENTS", env.get("RETRIEVER_LIMITS_EVENTS", "1000"))),
            states_days=int(env.get("RETRIEVER_LIMIT_STATES_DAYS", env.get("RETRIEVER_LIMITS_STATES_DAYS", "14"))),
        ),
        echo_sql=env.get("MEMORY_SQL_ECHO", "false").lower() in {"1", "true", "yes"},
        llm_api_base=env.get("LLM_API_BASE", "https://api.openai.com/v1"),
        llm_api_key=env.get("LLM_API_KEY") or env.get("OPENAI_API_KEY"),
        embeddings_api_base=env.get("EMBEDDINGS_API_BASE", env.get("LLM_API_BASE", "https://api.openai.com/v1")),
        embeddings_api_key=env.get("EMBEDDINGS_API_KEY") or env.get("LLM_API_KEY") or env.get("OPENAI_API_KEY"),
        http_timeout=float(env.get("MEMORY_HTTP_TIMEOUT", "15")),
    )
    return config


def create_engine_from_config(config: MemoryConfig) -> Engine:
    connect_args = {}
    if config.is_sqlite:
        connect_args["check_same_thread"] = False
    engine = create_engine(
        config.db_url,
        echo=config.echo_sql,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    return engine


__all__ = ["MemoryConfig", "RetrieverLimits", "load_memory_config", "create_engine_from_config"]
