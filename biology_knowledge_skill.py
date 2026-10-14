from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Optional

from core.contract.actions import normalize_step


def _norm(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _hash8(s: str) -> str:
    return hashlib.sha1(_norm(s).encode("utf-8")).hexdigest()[:8]


_BIO_RE = re.compile(
    r"\b("
    r"biyoloji|dna|rna|gen|kromozom|hücre|hucre|doku|organ|protein|enzim|"
    r"evrim|mitoz|mayoz|mitokondri|ribozom|bakteri|virüs|virus|fotosentez|solunum"
    r")\b",
    flags=re.IGNORECASE,
)

_BIO_Q_RE = re.compile(r"\b(nedir|ne demek|açıkla|acikla|neden|nasıl|nasil|kimdir|kim|görevi|gorevi)\b", re.IGNORECASE)

_OTHER_DOMAIN_RE = re.compile(
    r"\b(pisagor|integral|türev|turev|mol|molarite|asit|baz|volt|ohm|kuvvet|başkent|baskent)\b",
    re.IGNORECASE,
)

_NUMERIC_RE = re.compile(r"(=|\d|\bkaç\b|\bkac\b|\bhesapla\b)", re.IGNORECASE)


def try_parse_biology_knowledge(text: str) -> Optional[Dict[str, Any]]:
    q = _norm(text)
    if not q:
        return None
    low = q.lower()

    if _OTHER_DOMAIN_RE.search(low):
        return None
    if not _BIO_RE.search(low):
        return None
    if not _BIO_Q_RE.search(low):
        return None
    if _NUMERIC_RE.search(low):
        return None

    key = f"knowledge:biology:{_hash8(q)}"

    return normalize_step(
        {
            "type": "CMD",
            "cmd_type": "FETCH_API",
            "params": {
                "provider": "knowledge",
                "domain": "biology",
                "kind": "explain",
                "query": q,
                "key": key,
                "ttl_sec": 30 * 86400,
                "fallback_provider": "memory",
                "fallback_providers": ["memory"],
            },
            "priority": 0,
            "cancel_previous": False,
        }
    )