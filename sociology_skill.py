from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Optional

from core.contract.actions import normalize_step


def _norm(s: str) -> str:
    return (s or "").strip()


def _hash8(s: str) -> str:
    import hashlib as _h
    return _h.sha1(_norm(s).encode("utf-8")).hexdigest()[:8]


_SOC_RE = re.compile(
    r"\b(sosyoloji|toplum|kültür|kultur|norm|değer|deger|sınıf|sinif|tabakalaşma|tabakalaşma|sosyal)\b",
    re.I,
)


def try_parse_sociology(text: str) -> Optional[Dict[str, Any]]:
    t = _norm(text)
    if not t or not _SOC_RE.search(t):
        return None

    q = re.sub(r"\bmamula\b", "", t, flags=re.I).strip()
    key = f"knowledge:sociology:{_hash8(q)}"

    return normalize_step(
        {
            "type": "CMD",
            "cmd_type": "FETCH_API",
            "params": {
                "provider": "knowledge",
                "domain": "sociology",
                "kind": "explain",
                "query": q,
                "key": key,
                "ttl_sec": 30 * 24 * 3600,
                "fallback_provider": "memory",
                "fallback_providers": ["memory"],
            },
            "priority": 0,
            "cancel_previous": False,
            "note": "",
        }
    )