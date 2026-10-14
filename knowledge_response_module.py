# core/modules/knowledge_response_module.py
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from core.utils.knowledge_response_i18n import knowledge_msg_lang, knowledge_phrase
from core.utils.locale_resolution import resolve_voice_lang

_DOMAIN_ANSWER_KEYS = {
    "history": "answer_history",
    "geography": "answer_geography",
    "physics": "answer_physics",
    "chemistry": "answer_chemistry",
    "biology": "answer_biology",
    "math": "answer_math",
    "space": "answer_space",
}


def now_ms() -> int:
    return int(time.time() * 1000)


class KnowledgeResponseModule:
    """
    MAMULA knowledge response modulu.

    Gorev:
      - knowledge.result ve knowledge.query.result topic'lerini dinlemek
      - gelen bilgi sonucunu anlamli bir cevaba donusturmek
      - voice.say veya action.request ile yanit uretmek

    Ilk surum hedefleri:
      - basit bilgi cevabi
      - bulunamayan sonuc icin fallback
      - liste / coklu sonuc icin ozetleme
      - domain bazli kisa konusma uretimi
    """

    name = "knowledge_response"

    def __init__(self, bus, rt, speak_via_action: bool = False):
        self.bus = bus
        self.rt = rt
        self.speak_via_action = bool(speak_via_action)

        bus.subscribe("knowledge.result", self.on_knowledge_result)
        bus.subscribe("knowledge.query.result", self.on_knowledge_result)

    # ---------------------------
    # Lifecycle
    # ---------------------------

    def tick(self):
        self.rt.beat(self.name)

    # ---------------------------
    # Handlers
    # ---------------------------

    def on_knowledge_result(self, topic: str, msg: Any):
        payload = self._as_dict(msg)
        if not payload:
            return

        response = self._build_response(payload)
        if response is None:
            return

        self._emit_response(
            text=response["text"],
            correlation_id=response.get("correlation_id", ""),
            source_topic=topic,
            context=response,
        )

    # ---------------------------
    # Response builder
    # ---------------------------

    def _build_response(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        ok = bool(payload.get("ok", True))
        found = bool(payload.get("found", True))
        domain = str(payload.get("domain", "") or "").strip().lower()
        query = str(payload.get("query", "") or "").strip()
        correlation_id = self._extract_correlation_id(payload)
        lg = knowledge_msg_lang(payload)

        if not ok:
            return {
                "text": knowledge_phrase(lg, "error_process"),
                "correlation_id": correlation_id,
                "kind": "error",
                "lang": lg,
            }

        # tekil cevap
        if "answer" in payload:
            answer = payload.get("answer", None)
            if answer:
                return {
                    "text": self._format_single_answer(answer, lg, domain=domain, query=query),
                    "correlation_id": correlation_id,
                    "kind": "single_answer",
                    "lang": lg,
                }

        # generic value
        if "value" in payload:
            value = payload.get("value", None)
            if found and value is not None:
                return {
                    "text": self._format_single_answer(value, lg, domain=domain, query=query),
                    "correlation_id": correlation_id,
                    "kind": "value_answer",
                    "lang": lg,
                }

        # items / results listesi
        items = payload.get("items", None)
        if items is None:
            items = payload.get("results", None)

        if found and items:
            return {
                "text": self._format_result_list(items, lg, domain=domain, query=query),
                "correlation_id": correlation_id,
                "kind": "result_list",
                "lang": lg,
            }

        # hiçbir şey bulunamadı
        return {
            "text": self._fallback_not_found_text(lg, domain=domain, query=query),
            "correlation_id": correlation_id,
            "kind": "not_found",
            "lang": lg,
        }

    # ---------------------------
    # Formatters
    # ---------------------------

    def _format_single_answer(
        self, answer: Any, lang: str, domain: str = "", query: str = ""
    ) -> str:
        answer_text = self._to_speech_text(answer, lang)

        phrase_key = _DOMAIN_ANSWER_KEYS.get(domain)
        if phrase_key:
            return knowledge_phrase(lang, phrase_key, answer=answer_text)

        if query:
            return knowledge_phrase(lang, "answer_for_query", query=query, answer=answer_text)

        return answer_text

    def _format_result_list(self, items: Any, lang: str, domain: str = "", query: str = "") -> str:
        if not isinstance(items, list):
            return self._format_single_answer(items, lang, domain=domain, query=query)

        if not items:
            return self._fallback_not_found_text(lang, domain=domain, query=query)

        texts: List[str] = []
        for item in items[:3]:
            texts.append(self._to_speech_text(item, lang))

        joined = " | ".join(texts)

        if query:
            return knowledge_phrase(lang, "list_for_query", query=query, joined=joined)

        if domain:
            return knowledge_phrase(lang, "list_for_domain", domain=domain, joined=joined)

        return knowledge_phrase(lang, "list_generic", joined=joined)

    def _fallback_not_found_text(self, lang: str, domain: str = "", query: str = "") -> str:
        if query:
            return knowledge_phrase(lang, "not_found_query", query=query)
        if domain:
            return knowledge_phrase(lang, "not_found_domain", domain=domain)
        return knowledge_phrase(lang, "not_found_plain")

    # ---------------------------
    # Emitters
    # ---------------------------

    def _emit_response(
        self,
        text: str,
        correlation_id: str,
        source_topic: str,
        context: Optional[Dict[str, Any]] = None,
    ):
        meta = {
            "id": self._new_id("knowresp"),
            "ts_ms": now_ms(),
            "seq": 0,
            "source": self.name,
            "correlation_id": str(correlation_id or ""),
            "extra": {
                "source_topic": source_topic,
                "context_kind": str((context or {}).get("kind", "") or ""),
            },
        }

        self.bus.publish(
            "knowledge.response",
            {
                "text": text,
                "meta": meta,
                "context": context or {},
            },
        )

        ctx = context or {}
        lang = resolve_voice_lang(context_lang=ctx.get("lang") or ctx.get("locale"))
        if self.speak_via_action:
            self.bus.publish(
                "action.request",
                {
                    "action_type": "speech",
                    "action_id": self._new_id("act"),
                    "task_id": str(correlation_id or ""),
                    "priority": 35,
                    "blocking": False,
                    "reason": "knowledge_response_speech",
                    "params": {
                        "text": text,
                        "lang": lang,
                    },
                    "text": text,
                    "meta": meta,
                },
            )
        else:
            self.bus.publish(
                "voice.say",
                {
                    "text": text,
                    "lang": lang,
                    "meta": meta,
                },
            )

    # ---------------------------
    # Utils
    # ---------------------------

    def _extract_correlation_id(self, payload: Dict[str, Any]) -> str:
        meta = payload.get("meta", None)
        if isinstance(meta, dict):
            return str(meta.get("correlation_id", "") or "")
        return str(payload.get("correlation_id", "") or "")

    def _as_dict(self, msg: Any) -> Dict[str, Any]:
        if msg is None:
            return {}

        if isinstance(msg, dict):
            return dict(msg)

        out: Dict[str, Any] = {}
        for key in (
            "ok",
            "found",
            "domain",
            "query",
            "answer",
            "value",
            "items",
            "results",
            "meta",
            "correlation_id",
            "error",
        ):
            try:
                out[key] = getattr(msg, key)
            except Exception:
                pass
        return out

    def _to_speech_text(self, value: Any, lang: str = "tr") -> str:
        if value is None:
            return knowledge_phrase(lang, "to_empty")
        if isinstance(value, bool):
            return knowledge_phrase(lang, "to_bool_true" if value else "to_bool_false")
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            if not value:
                return knowledge_phrase(lang, "to_empty_list")
            return ", ".join(self._to_speech_text(x, lang) for x in value[:5])
        if isinstance(value, dict):
            # sık görülen alanları biraz daha insanî sırayla oku
            ordered_keys = ["title", "name", "answer", "summary", "value", "result"]
            used = []
            parts = []

            for k in ordered_keys:
                if k in value:
                    parts.append(f"{k}: {self._to_speech_text(value[k], lang)}")
                    used.append(k)

            for k, v in value.items():
                if k in used:
                    continue
                parts.append(f"{k}: {self._to_speech_text(v, lang)}")
                if len(parts) >= 5:
                    break

            return ", ".join(parts) if parts else knowledge_phrase(lang, "to_empty_object")

        return str(value)

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:10]}"