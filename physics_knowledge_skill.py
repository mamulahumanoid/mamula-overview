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


_PHYSICS_CORE_RE = re.compile(
    r"\b("
    r"fizik|newton|kuvvet|ivme|hız|hiz|sürat|surat|"
    r"enerji|iş|is|güç|guc|momentum|basınç|basinc|"
    r"elektrik|akım|akim|gerilim|direnç|direnc|voltaj|"
    r"manyetik|manyetizma|alan|çekim|cekim|yerçekimi|yercekimi|"
    r"ışık|isik|optik|dalga|frekans|genlik|"
    r"kuantum|relativite|rölativite|maxwell|faraday|tesla"
    r")\b",
    flags=re.IGNORECASE,
)

_PHYSICS_QUESTION_RE = re.compile(
    r"\b(nedir|ne demek|açıkla|acikla|neden|nasıl|nasil|kimdir|kim)\b",
    flags=re.IGNORECASE,
)

_OTHER_DOMAIN_RE = re.compile(
    r"\b("
    r"pisagor|integral|türev|turev|limit|denklem|matematik|"
    r"dna|rna|gen|hücre|hucre|enzim|biyoloji|"
    r"atom|mol|molarite|asit|baz|kimya|"
    r"türkiye|başkent|baskent|nehir|dağ|dag|ülke|ulke|şehir|sehir|coğrafya|cografya|"
    r"vestfalya|osmanlı|osmanli|cumhuriyet|tarih|"
    r"yapay zeka|demokrasi|sokrates|internet"
    r")\b",
    flags=re.IGNORECASE,
)

_NUMERIC_HINT_RE = re.compile(
    r"(=|\d|\bkaç\b|\bkac\b|\bhesapla\b|\bbul\b|\bçöz\b|\bcoz\b|\bkg\b|\bohm\b|\bvolt\b|\bamper\b)",
    flags=re.IGNORECASE,
)


def try_parse_physics_knowledge(text: str) -> Optional[Dict[str, Any]]:
    q = _norm(text)
    if not q:
        return None

    low = q.lower()

    if _OTHER_DOMAIN_RE.search(low):
        return None
    if not _PHYSICS_CORE_RE.search(low):
        return None
    if not _PHYSICS_QUESTION_RE.search(low):
        return None
    if _NUMERIC_HINT_RE.search(low):
        return None

    key = f"knowledge:physics:{_hash8(q)}"

    return normalize_step(
        {
            "type": "CMD",
            "cmd_type": "FETCH_API",
            "params": {
                "provider": "knowledge",
                "domain": "physics",
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