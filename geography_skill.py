from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, Optional

from core.contract.actions import normalize_step
from core.skills.text_norm import fold_tr, strip_wakeword_tr, normalize_knowledge_query


def _hash8(s: str) -> str:
    return hashlib.sha1((s or "").encode("utf-8")).hexdigest()[:8]


def _say(text: str) -> Dict[str, Any]:
    return normalize_step(
        {
            "type": "CMD",
            "cmd_type": "SAY",
            "params": {"text": text},
            "priority": 0,
            "cancel_previous": False,
        }
    )


def _fetch(query: str) -> Dict[str, Any]:
    raw = strip_wakeword_tr(query).strip()
    q = normalize_knowledge_query(raw) or raw
    return normalize_step(
        {
            "type": "CMD",
            "cmd_type": "FETCH_API",
            "params": {
                "provider": "knowledge",
                "domain": "geography",
                "kind": "explain",
                "query": q,
                "key": f"knowledge:geography:{_hash8(q)}",
                "ttl_sec": 30 * 86400,
                "fallback_provider": "memory",
                "fallback_providers": ["memory"],
            },
            "priority": 0,
            "cancel_previous": False,
        }
    )


_GEO_RE = re.compile(
    r"\b("
    r"coğrafya|cografya|coğrafi|cografi|başkent|baskent|şehir|sehir|ülke|ulke|"
    r"nehir|nehr|göl|gol|dağ|dag|kıta|kita|konum|bolge|bölge|"
    r"istanbul|ankara|madrid|everest|nil|ege|akdeniz|karadeniz|ic anadolu|iç anadolu|"
    r"türkiye|turkiye|avrupa|asya|afrika"
    r")\b",
    flags=re.IGNORECASE,
)

_Q_RE = re.compile(
    r"\b("
    r"nedir|nerededir|neresidir|açıkla|acikla|önemi nedir|onemi nedir|"
    r"başkenti|baskenti|konumu|hangi ulkede|hangi ülkede|hangi kitada|hangi kıtada|hang ulke|hang kita"
    r")\b",
    flags=re.IGNORECASE,
)

_Q_PHRASES = (
    "hangi ulkede",
    "hangi ülkede",
    "hangi kitada",
    "hangi kıtada",
    "hang ulke",
    "hang kita",
)


def try_parse_geography(text: str) -> Optional[Dict[str, Any]]:
    raw = strip_wakeword_tr(text)
    t = fold_tr(raw)
    if not t:
        return None

    if not _GEO_RE.search(t):
        return None

    if not (_Q_RE.search(t) or any(p in t for p in _Q_PHRASES)):
        return None

    is_turkiye = any(x in t for x in ("turk", "türk", "turkiye", "türkiye"))
    is_baskent = any(x in t for x in ("baskent", "başkent", "baskenti", "başkenti"))

    if is_turkiye and is_baskent:
        return _say("Türkiye'nin başkenti Ankara'dır.")

    if "ankara" in t and any(x in t for x in ("nerede", "nerededir", "neresidir")):
        return _say(
            "Ankara, Türkiye'nin İç Anadolu Bölgesi'nde yer alır ve ülkenin başkentidir."
        )

    if "istanbul" in t and any(x in t for x in ("nerede", "nerededir", "neresidir")):
        return _say(
            "İstanbul, Türkiye'nin kuzeybatısında yer alır ve Avrupa ile Asya kıtalarını birleştiren şehirdir."
        )

    if "everest" in t:
        return _say("Everest, Himalayalar'da Nepal ile Tibet sınırında yer alır.")

    if "nil nehri" in t and any(x in t for x in ("onemi", "önemi")):
        return _say(
            "Nil Nehri, özellikle Eski Mısır uygarlığının tarım, ulaşım ve yerleşim düzeni açısından çok önemlidir."
        )

    if "nil nehri" in t and any(x in t for x in ("nerede", "nerededir", "neresidir")):
        return _say(
            "Nil Nehri Afrika kıtasında bulunur ve kuzeye doğru akarak Akdeniz'e dökülür."
        )

    if is_turkiye and any(x in t for x in ("cografi konum", "coğrafi konum", "konum")):
        return _say(
            "Türkiye, Asya ile Avrupa arasında yer alır. Üç tarafı denizlerle çevrilidir ve jeopolitik açıdan önemli bir geçiş konumundadır."
        )

    if "madrid" in t:
        return _say(
            "Madrid, İspanya'nın başkentidir ve ülkenin iç kesimlerinde yer alır."
        )

    if ("ege bolge" in t) and any(
        x in t for x in ("nerede", "nerededir", "neresidir", "hangi")
    ):
        return _say(
            "Ege Bölgesi, Türkiye'nin batısında yer alır ve Ege Denizi kıyısında konumlanır."
        )

    return _fetch(raw)