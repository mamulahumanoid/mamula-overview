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
    q = normalize_knowledge_query(query) or strip_wakeword_tr(query)
    return normalize_step(
        {
            "type": "CMD",
            "cmd_type": "FETCH_API",
            "params": {
                "provider": "knowledge",
                "domain": "math",
                "kind": "explain",
                "query": q,
                "key": f"knowledge:math:{_hash8(q)}",
                "ttl_sec": 30 * 86400,
                "fallback_provider": "memory",
                "fallback_providers": ["memory"],
            },
            "priority": 0,
            "cancel_previous": False,
        }
    )


_MATH_INFO_RE = re.compile(
    r"\b("
    r"matematik|pisagor|teorem|teoremi|limit|integral|türev|turev|"
    r"denklem|fonksiyon|olasılık|olasilik|istatistik|matris|vektör|vektor|"
    r"geometri|trigonometri|logaritma|pi"
    r")\b",
    flags=re.IGNORECASE,
)

_INFO_Q_RE = re.compile(
    r"\b(nedir|ne demek|açıkla|acikla|neden|önemi nedir|onemi nedir|kimdir)\b",
    flags=re.IGNORECASE,
)

_COMPUTE_RE = re.compile(
    r"(=|\d|\bkaç\b|\bkac\b|\bkaçtır\b|\bkactir\b|\bhesapla\b|\bçöz\b|\bcoz\b|\bkere\b)",
    flags=re.IGNORECASE,
)


def try_parse_math_knowledge(text: str) -> Optional[Dict[str, Any]]:
    t = fold_tr(strip_wakeword_tr(text))
    if not t:
        return None

    if not _MATH_INFO_RE.search(t):
        return None

    # işlem sorularını math_skill'e bırak
    if _COMPUTE_RE.search(t):
        return None

    if not _INFO_Q_RE.search(t):
        return None

    if "pisagor" in t and ("teorem" in t or "teoremi" in t):
        return _say(
            "Pisagor teoremi, dik üçgende hipotenüsün karesinin diğer iki dik kenarın "
            "kareleri toplamına eşit olduğunu söyler. Yani a kare artı b kare eşittir c kare."
        )

    if re.search(r"\blimit\b", t):
        return _say(
            "Limit, bir fonksiyonun girdisi belli bir değere yaklaşırken çıktısının hangi "
            "değere yaklaştığını inceleyen kavramdır."
        )

    if re.search(r"\b(türev|turev)\b", t):
        return _say(
            "Türev, bir fonksiyonun anlık değişim hızını verir. Geometrik olarak eğrinin "
            "bir noktadaki teğet eğimini ifade eder."
        )

    if re.search(r"\bintegral\b", t):
        return _say(
            "İntegral, birikimi ve alanı hesaplamak için kullanılır. Belirli integral "
            "eğri altındaki alanı, belirsiz integral ise türevin tersini temsil eder."
        )

    if re.search(r"\bfonksiyon\b", t):
        return _say(
            "Fonksiyon, her girdiye karşılık bir çıktı üreten matematiksel ilişkidir."
        )

    if re.search(r"\bdenklem\b", t):
        return _say(
            "Denklem, bilinmeyen içeren ve iki ifadenin eşitliğini gösteren matematiksel ifadedir."
        )

    if re.search(r"\bolasılık\b|\bolasilik\b", t):
        return _say(
            "Olasılık, bir olayın gerçekleşme ihtimalini sayısal olarak ifade eder. "
            "Değeri sıfır ile bir arasındadır."
        )

    if re.search(r"\bistatistik\b", t):
        return _say(
            "İstatistik, verilerin toplanması, düzenlenmesi, analiz edilmesi ve yorumlanmasıyla ilgilenir."
        )

    if re.search(r"\bmatris\b", t):
        return _say(
            "Matris, sayıların satır ve sütunlar halinde düzenlenmiş biçimidir."
        )

    if re.search(r"\b(trigonometri)\b", t):
        return _say(
            "Trigonometri, açıları ve üçgen kenarları arasındaki ilişkileri inceler. "
            "Sinüs, kosinüs ve tanjant temel trigonometrik fonksiyonlardır."
        )

    if re.search(r"\blogaritma\b", t):
        return _say(
            "Logaritma, üstel işlemin tersidir. Örneğin log taban iki sekiz eşittir üçtür."
        )

    if re.search(r"\bgeometri\b", t):
        return _say(
            "Geometri, şekilleri, uzunlukları, açıları, alanları ve uzaydaki ilişkileri inceleyen matematik dalıdır."
        )

    if re.search(r"\bpi\b", t):
        return _say(
            "Pi sayısı, bir çemberin çevresinin çapına oranıdır. Yaklaşık değeri 3.14'tür."
        )

    return _fetch(t)