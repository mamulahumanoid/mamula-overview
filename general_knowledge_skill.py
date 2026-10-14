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


_GENERAL_Q_RE = re.compile(
    r"\b("
    r"nedir|ne demek|açıkla|acikla|neden|nasıl|nasil|kimdir|kim|"
    r"ne zaman|nerede|nerededir|önemi|onemi|önemlidir|onemlidir|"
    r"görevi|gorevi|özellikleri|ozellikleri"
    r")\b",
    flags=re.IGNORECASE,
)

_EXCLUDE_DOMAIN_RE = re.compile(
    r"\b("
    r"matematik|pisagor|integral|türev|turev|limit|denklem|"
    r"fizik|newton|kuvvet|ivme|enerji|akım|akim|volt|ohm|"
    r"kimya|atom|mol|molarite|asit|baz|"
    r"biyoloji|dna|rna|hücre|hucre|enzim|mitokondri|"
    r"tarih|vestfalya|osmanlı|osmanli|cumhuriyet|"
    r"coğrafya|cografya|başkent|baskent|nehir|dağ|dag|ülke|ulke|şehir|sehir|everest|nil"
    r")\b",
    flags=re.IGNORECASE,
)

_EXCLUDE_NUMERIC_RE = re.compile(
    r"(=|\d|\bkaç\b|\bkac\b|\bhesapla\b|\bçöz\b|\bcoz\b|\bhava durumu\b)",
    flags=re.IGNORECASE,
)


def try_parse_general_knowledge(text: str) -> Optional[Dict[str, Any]]:
    q = _norm(text)
    if not q:
        return None

    low = q.lower()

    if not _GENERAL_Q_RE.search(low):
        return None
    if _EXCLUDE_DOMAIN_RE.search(low):
        return None
    if _EXCLUDE_NUMERIC_RE.search(low):
        return None

    key = f"knowledge:general:{_hash8(q)}"

    return normalize_step(
        {
            "type": "CMD",
            "cmd_type": "FETCH_API",
            "params": {
                "provider": "knowledge",
                "domain": "general",
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