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


_CHEM_CORE_RE = re.compile(
    r"\b("
    r"kimya|atom|molekül|molekul|iyon|proton|nötron|notron|elektron|"
    r"asit|baz|tuz|ph|reaksiyon|çözünürlük|cozunurluk|denge|"
    r"periyodik|element|bileşik|bilesik|kimyasal|organik|inorganik|"
    r"avogadro|mol|bağ|bag|oksidasyon|indirgenme"
    r")\b",
    flags=re.IGNORECASE,
)

_CHEM_Q_RE = re.compile(
    r"\b(nedir|ne demek|açıkla|acikla|neden|nasıl|nasil|kimdir|kim)\b",
    flags=re.IGNORECASE,
)

_OTHER_DOMAIN_RE = re.compile(
    r"\b("
    r"pisagor|integral|türev|turev|limit|denklem|matematik|"
    r"dna|rna|gen|hücre|hucre|enzim|biyoloji|"
    r"volt|ohm|amper|akım|akim|kuvvet|ivme|newton|fizik|"
    r"başkent|baskent|nehir|dağ|dag|ülke|ulke|şehir|sehir|coğrafya|cografya|"
    r"vestfalya|osmanlı|osmanli|cumhuriyet|tarih|"
    r"yapay zeka|demokrasi|internet|sokrates"
    r")\b",
    flags=re.IGNORECASE,
)

_NUMERIC_HINT_RE = re.compile(
    r"(=|\d|\bkaç\b|\bkac\b|\bhesapla\b|\bbul\b|\bçöz\b|\bcoz\b|\blitre\b|\bgram\b)",
    flags=re.IGNORECASE,
)


def try_parse_chemistry_knowledge(text: str) -> Optional[Dict[str, Any]]:
    q = _norm(text)
    if not q:
        return None

    low = q.lower()

    if _OTHER_DOMAIN_RE.search(low):
        return None
    if not _CHEM_CORE_RE.search(low):
        return None
    if not _CHEM_Q_RE.search(low):
        return None
    if _NUMERIC_HINT_RE.search(low):
        return None

    key = f"knowledge:chemistry:{_hash8(q)}"

    return normalize_step(
        {
            "type": "CMD",
            "cmd_type": "FETCH_API",
            "params": {
                "provider": "knowledge",
                "domain": "chemistry",
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