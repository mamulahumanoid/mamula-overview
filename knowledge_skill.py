from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple, Optional

from core.contract.actions import normalize_step
from core.skills.skill_base import SkillMatch, Step


def _norm(s: str) -> str:
    return (s or "").strip()


def _strip_wakeword_tr(s: str) -> str:
    return re.sub(r"\bmamula\b", "", s, flags=re.IGNORECASE).strip()


def _simplify_query_tr(text: str) -> str:
    q = _strip_wakeword_tr(_norm(text)).lower()
    q = re.sub(
        r"\b(neden|niçin|niye|önemlidir|onemlidir|önemi|onemi|nedir|kimdir|ne\s*zaman|açıkla|acikla|"
        r"sonuçları|sonuclari|etkileri|farkı|farki)\b",
        "",
        q,
        flags=re.IGNORECASE,
    )
    q = re.sub(r"\s+", " ", q).strip()
    return q


_HINT_RE = re.compile(
    r"\b(nedir|kimdir|ne\s*zaman|ne\s*oldu|nerede|neden|nas[ıi]l|a[çc]ıkla|"
    r"form[üu]l|teorem|kanıtla|ispat|çöz|hesapla|integral|türev|limit|denklem|"
    r"tarih|coğrafya|fizik|kimya|biyoloji|matematik|uzay|astronomi|gezegen|galaksi)\b",
    flags=re.IGNORECASE,
)

_DOMAIN_RULES: List[Tuple[str, re.Pattern]] = [
    (
        "history",
        re.compile(
            r"\b(tarih|ne\s*zaman|sava[şs]|imparator|padi[şs]ah|osmanl[ıi]|cumhuriyet|"
            r"devrim|ihtilal|ferman|antlaşma|antlasma|antlaşması|antlasmasi|"
            r"çağ|cag|dönem|donem|vestfalya|lozan|sevr|mondros|malazgirt|çanakkale|"
            r"atatürk|ataturk|fatih|kanuni|yavuz|roma|fransız|fransiz|sanayi)\b",
            re.I,
        ),
    ),
    ("geography", re.compile(r"\b(coğrafya|cografya|nerede|başkent|baskent|ülke|ulke|kıta|kita|şehir|sehir|dağ|dag|nehir|harita)\b", re.I)),
    ("physics", re.compile(r"\b(fizik|newton|kuvvet|ivme|hız|hiz|enerji|momentum|kütle|kutle|basınç|basinc|elektrik|manyetik|ışık|isik)\b", re.I)),
    ("chemistry", re.compile(r"\b(kimya|atom|molek[üu]l|reaksiyon|mol\b|ph\b|asid|asit|baz|periyodik)\b", re.I)),
    ("biology", re.compile(r"\b(biyoloji|h[üu]cre|dna\b|rna\b|enzim|evrim|protein|bakteri|vir[üu]s)\b", re.I)),
    ("math", re.compile(r"\b(matematik|integral|türev|turev|limit|denklem|fonksiyon|olasılık|olasilik|istatistik|matris|vekt[öo]r)\b", re.I)),
    ("space", re.compile(r"\b(uzay|astronomi|nasa|mars|j[üu]piter|sat[üu]rn|gezegen|uydu|yıldız|yildiz|galaksi|evren|kara\s*delik)\b", re.I)),
    ("sociology", re.compile(r"\b(sosyoloji|toplum|kültür|kultur|norm|değer|deger|sınıf|sinif|tabakalaşma|tabakalaşma|sosyal)\b", re.I)),
]


def infer_domain_tr(text: str) -> str:
    t = _norm(text).lower()
    for domain, rx in _DOMAIN_RULES:
        if rx.search(t):
            return domain
    return "general"


def infer_kind_tr(text: str) -> str:
    t = _norm(text).lower()
    if re.search(r"\b(çöz|coz|hesapla|integral|türev|turev|limit|denklem|problem|soru)\b", t, re.I):
        return "problem_solution"
    if re.search(r"\b(neden|nasıl|nasil|a[çc]ıkla|mekanizma|nas[ıi]l\s*çalışır|nasil\s*calisir)\b", t, re.I):
        return "explain"
    return "fact"


def _hash8(s: str) -> str:
    import hashlib
    return hashlib.sha1(_norm(s).encode("utf-8")).hexdigest()[:8]


class KnowledgeSkill:
    name = "knowledge"

    def match(self, text: str) -> SkillMatch | None:
        if _HINT_RE.search(_norm(text)):
            return SkillMatch(matched=True, reason="hint_regex")
        return None

    def to_steps(self, text: str) -> List[Step]:
        q = _simplify_query_tr(text)
        if not q:
            q = _strip_wakeword_tr(_norm(text))

        domain = infer_domain_tr(q)
        kind = infer_kind_tr(_norm(text))

        key = f"knowledge:{kind}:{domain}:{_hash8(q)}"

        ttl = 86400
        if kind == "fact":
            ttl = 7 * 86400
        elif kind in ("explain", "problem_solution"):
            ttl = 30 * 86400

        return [
            normalize_step(
                {
                    "type": "CMD",
                    "cmd_type": "FETCH_API",
                    "params": {
                        "provider": "knowledge",
                        "domain": domain,
                        "kind": kind,
                        "query": q,
                        "key": key,
                        "ttl_sec": ttl,
                        "fallback_provider": "memory",
                        "fallback_providers": ["memory"],
                    },
                    "priority": 0,
                    "cancel_previous": False,
                    "note": "",
                }
            )
        ]


def try_parse_knowledge(text: str) -> Optional[Dict[str, Any] | List[Dict[str, Any]]]:
    skill = KnowledgeSkill()
    m = skill.match(text)
    if m is None:
        return None
    return skill.to_steps(text)