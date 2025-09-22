from __future__ import annotations

import hashlib
import re
from typing import Iterable, Optional


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    slug = _SLUG_RE.sub("_", value.lower()).strip("_")
    return slug or "item"


def _hash_for(parts: Iterable[str]) -> str:
    joined = "::".join(part.strip().lower() for part in parts if part)
    digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()
    return digest[:10]


def entity_id(kind: str, name: Optional[str] = None, qualifiers: Optional[Iterable[str]] = None) -> str:
    qualifiers = tuple(qualifiers or ())
    base_parts = [kind]
    if name:
        base_parts.append(slugify(name))
    if qualifiers:
        base_parts.extend(slugify(q) for q in qualifiers if q)
    canonical = ":".join(base_parts)
    hashed = _hash_for([kind, *(name or "",), *qualifiers])
    return f"{canonical}:{hashed}"


def person_id(full_name: str, qualifiers: Optional[Iterable[str]] = None) -> str:
    return entity_id("person", full_name, qualifiers)


def wallet_id(owner: str, wallet_name: str | None = None) -> str:
    qualifiers = [slugify(owner)]
    if wallet_name:
        qualifiers.append(slugify(wallet_name))
    return entity_id("wallet", "wallet", qualifiers)


def property_id(address: str) -> str:
    return entity_id("property", address)


def business_id(name: str) -> str:
    return entity_id("business", name)


def security_id(symbol: str) -> str:
    return entity_id("security", symbol)


__all__ = [
    "slugify",
    "entity_id",
    "person_id",
    "wallet_id",
    "property_id",
    "business_id",
    "security_id",
]
