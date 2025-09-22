from __future__ import annotations

import hashlib
import json
import logging
import math
import random
from typing import Iterable, List, Sequence

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import MemoryConfig

logger = logging.getLogger(__name__)


def _rng_for_text(text: str) -> random.Random:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big")
    return random.Random(seed)


def _normalize(vector: Sequence[float]) -> List[float]:
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def _pad_or_trim(vector: Sequence[float], dim: int) -> List[float]:
    values = list(float(v) for v in vector)
    if len(values) == dim:
        return values
    if len(values) > dim:
        return values[:dim]
    values.extend([0.0] * (dim - len(values)))
    return values


def _remote_embed(text: str, config: MemoryConfig) -> List[float]:
    base = config.embeddings_api_base.rstrip("/")
    endpoint = f"{base}/embeddings"
    headers = {
        "Authorization": f"Bearer {config.embeddings_api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": config.embeddings_model, "input": text}
    with httpx.Client(timeout=config.http_timeout) as client:
        response = client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
    try:
        vector = data["data"][0]["embedding"]
    except (KeyError, IndexError) as exc:  # pragma: no cover - defensive
        raise ValueError(f"Unexpected embedding response: {json.dumps(data)[:200]}") from exc
    return _normalize(_pad_or_trim(vector, config.vector_dim))


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.2, min=0.2, max=2))
def embed_text(text: str, config: MemoryConfig) -> List[float]:
    if config.embeddings_enabled:
        try:
            return _remote_embed(text, config)
        except Exception as exc:  # pragma: no cover - network failures
            logger.warning("memory.embeddings.remote_failed", exc_info=exc)
    rng = _rng_for_text(f"{config.embeddings_model}:{text}")
    values = [rng.uniform(-1.0, 1.0) for _ in range(config.vector_dim)]
    return _normalize(values)


def embed_batch(texts: Iterable[str], config: MemoryConfig) -> List[List[float]]:
    return [embed_text(text, config) for text in texts]


__all__ = ["embed_text", "embed_batch"]
