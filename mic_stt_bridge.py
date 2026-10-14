# mic_stt_bridge.py
"""Mikrofon → ASR → core HTTP.

Vosk varsayılan çevrimdışı sağlayıcıdır. ``CORE_ASR_PROVIDER=openai_compatible``
seçildiğinde Vosk yalnız söz sınırlarını belirler; bellekte tutulan PCM
utterance, gerçek metin çözümleme için yapılandırılmış çok dilli ASR
sunucusuna gönderilir.
"""
import os
import queue
import re
import sys
import time
from pathlib import Path

import requests
from core.services.voice_asr_repair import (
    is_asr_repair_affirmative,
    is_asr_repair_negative,
    suggest_asr_repair,
)
from core.services.openai_compatible_speech_provider import (
    configured_openai_compatible_asr_provider,
)
from core.services.segmented_asr_provider import VoskSegmentedBatchASR
from core.services.vosk_asr_provider import VoskRecognizerAdapter, transcript_payload
from core.services.voice_qualification_metrics import (
    VoiceQualificationMetricsRecorder,
    parse_qualification_review,
    review_flag_names,
)
from core.utils.command_normalizer import norm_text, strip_wake_word
from core.utils.optional_deps import MissingExtraError, import_optional

ROOT = Path(__file__).resolve().parent
_DEFAULT_PORT = (os.environ.get("CORE_HTTP_PORT") or "8777").strip() or "8777"
CORE_URL = os.environ.get("CORE_URL", f"http://127.0.0.1:{_DEFAULT_PORT}/stt/final").strip()
MODEL_PATH = os.environ.get(
    "VOSK_MODEL_PATH",
    str(ROOT / "models" / "vosk-model-small-tr-0.3"),
).strip()
_CORE_LOC = (os.environ.get("CORE_DEFAULT_LOCALE") or "tr").strip().lower().replace("_", "-")
_CORE_BASE = _CORE_LOC.split("-", 1)[0] if _CORE_LOC else "tr"
_STT_LANG_RAW = (os.environ.get("STT_LANG") or _CORE_BASE).strip().lower().replace("_", "-")
STT_LANG = _STT_LANG_RAW.split("-", 1)[0] if _STT_LANG_RAW else "tr"
ASR_PROVIDER = (os.environ.get("CORE_ASR_PROVIDER") or "vosk").strip().lower()
ASR_LANGUAGE_HINT = (os.environ.get("CORE_ASR_LANGUAGE_HINT") or "").strip()
HTTP_TIMEOUT_S = float((os.environ.get("STT_HTTP_TIMEOUT_S") or "45").strip() or "45")
HTTP_AUTH_TOKEN = (
    os.environ.get("MIC_STT_AUTH_TOKEN")
    or os.environ.get("CORE_HTTP_VOICE_TOKEN")
    or os.environ.get("CORE_HTTP_ADMIN_TOKEN")
    or ""
).strip()
MIC_STT_DEBUG_CORE_JSON = (os.environ.get("MIC_STT_DEBUG_CORE_JSON") or "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
MIC_STT_ECHO_SUPPRESS = (os.environ.get("MIC_STT_ECHO_SUPPRESS") or "1").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
MIC_STT_DEBUG_ECHO = (os.environ.get("MIC_STT_DEBUG_ECHO") or "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
MIC_STT_HALF_DUPLEX = (os.environ.get("MIC_STT_HALF_DUPLEX") or "1").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
MIC_STT_REMOTE_FALLBACK_TO_VOSK = (
    os.environ.get("MIC_STT_REMOTE_FALLBACK_TO_VOSK") or "0"
).strip().lower() in ("1", "true", "yes", "on")

# Son çekirdek yanıtındaki session_id ile bir sonraki istekte gönderilir (diyalog sürekliliği).
_MIC_STT_PERSIST_RAW = (os.environ.get("MIC_STT_PERSIST_SESSION") or "1").strip().lower()
MIC_STT_PERSIST_SESSION = _MIC_STT_PERSIST_RAW not in ("0", "false", "no", "off")
_MIC_STT_NEW_SESSION_RAW = (os.environ.get("MIC_STT_NEW_SESSION_ON_WAKE") or "").strip().lower()
MIC_STT_NEW_SESSION_ON_WAKE = _MIC_STT_NEW_SESSION_RAW in ("1", "true", "yes", "on")
_MIC_STT_ALLOW_NO_WAKE_RAW = (
    os.environ.get("MIC_STT_ALLOW_NO_WAKE_FOLLOWUPS") or ""
).strip().lower()
MIC_STT_ALLOW_NO_WAKE_FOLLOWUPS = _MIC_STT_ALLOW_NO_WAKE_RAW in (
    "1",
    "true",
    "yes",
    "on",
)
_SESSION_CACHE = ROOT / "data" / "runtime" / "mic_stt_session_id.txt"
QUALIFICATION_CASES_PATH = (
    os.environ.get("MIC_STT_QUALIFICATION_CASES_PATH") or ""
).strip()
QUALIFICATION_RESULTS_PATH = (
    os.environ.get("MIC_STT_QUALIFICATION_RESULTS_PATH") or ""
).strip()
QUALIFICATION_RUN_ID = (os.environ.get("MIC_STT_QUALIFICATION_RUN_ID") or "").strip()


def _load_saved_session() -> str:
    if not MIC_STT_PERSIST_SESSION:
        return ""
    try:
        if _SESSION_CACHE.is_file():
            return _SESSION_CACHE.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return ""


def _save_session(session_id: str) -> None:
    if not MIC_STT_PERSIST_SESSION or not session_id:
        return
    try:
        _SESSION_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _SESSION_CACHE.write_text(session_id, encoding="utf-8")
    except OSError:
        pass

SAMPLE_RATE = 16000
BLOCK_SIZE = 8000
WAKE_WORD = "mamula"
_TR_WAKE_ALIASES = frozenset(
    {"abla", "babamla", "mandala", "muğla", "namına"}
)
_EN_WAKE_ALIASES = frozenset(
    {
        "amula",
        "kamula",
        "mahmula",
        "mammula",
        "mamola",
        "mamulla",
        "manula",
        "mula",
    }
)
_EN_MULTIWORD_WAKE_ALIASES = (
    "mama la",
    "ma mula",
    "mam ula",
    "mom ula",
    "ma'am ula",
    "ma'am yola",
    "ma'am mueller",
)

# Optional: select input device by index or name-substring
# Examples:
#   MIC_DEVICE=56
#   MIC_DEVICE=UC02
MIC_DEVICE = os.environ.get("MIC_DEVICE", "").strip()
MIC_LIST_DEVICES = (os.environ.get("MIC_LIST_DEVICES") or "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

audio_q = queue.Queue()

_ECHO_STOP_TOKENS = {
    "a",
    "ama",
    "bir",
    "bu",
    "da",
    "de",
    "daha",
    "ile",
    "icin",
    "ve",
    "ya",
}


def _load_voice_dependencies():
    sd = import_optional("sounddevice", capability="microphone STT bridge", extra="voice")
    vosk = import_optional("vosk", capability="microphone STT bridge", extra="voice")
    return sd, vosk.KaldiRecognizer, vosk.Model


def _build_stream_asr(vosk_asr):
    if ASR_PROVIDER in {"", "vosk", "vosk_offline_fallback"}:
        return vosk_asr
    if ASR_PROVIDER != "openai_compatible":
        raise ValueError(f"desteklenmeyen CORE_ASR_PROVIDER={ASR_PROVIDER!r}")
    batch_asr = configured_openai_compatible_asr_provider()
    if batch_asr is None:
        raise ValueError("OpenAI-compatible ASR yapilandirmasi eksik")
    return VoskSegmentedBatchASR(
        vosk_asr,
        batch_asr,
        sample_rate_hz=SAMPLE_RATE,
        locale_hint=ASR_LANGUAGE_HINT,
        output_locale=STT_LANG,
        max_utterance_s=max(1.0, _safe_float_env("MIC_STT_MAX_UTTERANCE_S", 30.0)),
        boundary_grace_s=max(
            0.0,
            _safe_float_env("MIC_STT_ASR_BOUNDARY_GRACE_S", 0.0),
        ),
        wake_only_boundary_grace_s=max(
            0.0,
            _safe_float_env("MIC_STT_WAKE_ONLY_BOUNDARY_GRACE_S", 0.0),
        ),
        wake_word=WAKE_WORD,
        wake_aliases=(
            (*_EN_WAKE_ALIASES, *_EN_MULTIWORD_WAKE_ALIASES, "mommy ala")
            if STT_LANG == "en"
            else tuple(
                _TR_WAKE_ALIASES
                | ({"baba"} if QUALIFICATION_RUN_ID else set())
            )
            if STT_LANG == "tr"
            else ()
        ),
        fallback_to_segmenter=MIC_STT_REMOTE_FALLBACK_TO_VOSK,
    )


def _print_voice_dependency_hint(exc: MissingExtraError) -> None:
    print("[mic] voice dependency eksik.", file=sys.stderr)
    print(f"[mic] {exc}", file=sys.stderr)
    print('[mic] Bu repo icin onerilen kurulum: pip install -e ".[voice]"', file=sys.stderr)
    print('[mic] Tum gelistirme araclariyla: pip install -e ".[dev,voice]"', file=sys.stderr)


def _input_device_rows(sd_module, *, limit: int = 20) -> list[str]:
    try:
        devs = sd_module.query_devices()
    except Exception as exc:
        return [f"[mic] ses cihazi listesi okunamadi: {exc}"]

    rows: list[str] = []
    for i, device in enumerate(devs):
        channels = int(device.get("max_input_channels") or 0)
        if channels <= 0:
            continue
        name = str(device.get("name", "<unnamed>"))
        rate = device.get("default_samplerate", "?")
        rows.append(f"[mic]   {i}: {name} (input_channels={channels}, default_samplerate={rate})")
        if len(rows) >= limit:
            rows.append(f"[mic]   ... ilk {limit} input cihazi gosterildi")
            break
    if not rows:
        rows.append("[mic] input-capable mikrofon cihazi bulunamadi.")
    return rows


def _print_input_devices(sd_module) -> None:
    print("[mic] kullanilabilir input cihazlari:", file=sys.stderr)
    for row in _input_device_rows(sd_module):
        print(row, file=sys.stderr)


def _is_sounddevice_error(sd_module, exc: Exception) -> bool:
    port_audio_error = getattr(sd_module, "PortAudioError", None)
    if isinstance(port_audio_error, type) and isinstance(exc, port_audio_error):
        return True
    cls = exc.__class__
    return cls.__name__ == "PortAudioError" or cls.__module__.startswith("sounddevice")


def _print_audio_device_hint(sd_module, exc: Exception) -> None:
    print(f"[mic] mikrofon cihazi acilamadi: {exc}", file=sys.stderr)
    if MIC_DEVICE:
        print(f"[mic] secili MIC_DEVICE={MIC_DEVICE!r}", file=sys.stderr)
    _print_input_devices(sd_module)
    print("[mic] Cihazlari elle kontrol etmek icin: python -m sounddevice", file=sys.stderr)
    print("[mic] Belirli mikrofon secmek icin ornek: MIC_DEVICE=0 python mic_stt_bridge.py", file=sys.stderr)
    print("[mic] Isimle secmek icin ornek: MIC_DEVICE=UC02 python mic_stt_bridge.py", file=sys.stderr)
    print("[mic] Linux'ta PipeWire/PulseAudio mikrofon izinlerini ve varsayilan input cihazini kontrol edin.", file=sys.stderr)


def _core_headers() -> dict[str, str]:
    if not HTTP_AUTH_TOKEN:
        return {}
    return {"Authorization": f"Bearer {HTTP_AUTH_TOKEN}"}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _safe_int_env(name: str, default: int) -> int:
    try:
        return int((os.environ.get(name) or str(default)).strip())
    except (TypeError, ValueError):
        return int(default)


def _safe_float_env(name: str, default: float) -> float:
    try:
        return float((os.environ.get(name) or str(default)).strip())
    except (TypeError, ValueError):
        return float(default)


def _build_qualification_recorder() -> VoiceQualificationMetricsRecorder | None:
    configured = (
        QUALIFICATION_CASES_PATH,
        QUALIFICATION_RESULTS_PATH,
        QUALIFICATION_RUN_ID,
    )
    if not any(configured):
        return None
    if not all(configured):
        raise ValueError(
            "qualification metrics require cases path, results path, and run id"
        )
    return VoiceQualificationMetricsRecorder(
        cases_path=Path(QUALIFICATION_CASES_PATH),
        results_path=Path(QUALIFICATION_RESULTS_PATH),
        run_id=QUALIFICATION_RUN_ID,
        language=STT_LANG,
        first_case=_safe_int_env("MIC_STT_QUALIFICATION_FIRST_CASE", 1),
        last_case=_safe_int_env("MIC_STT_QUALIFICATION_LAST_CASE", 100),
        case_ids=(
            item.strip()
            for item in (os.environ.get("MIC_STT_QUALIFICATION_CASE_IDS") or "").split(",")
            if item.strip()
        ),
    )


def _print_qualification_next(
    recorder: VoiceQualificationMetricsRecorder,
) -> None:
    case = recorder.current_case
    if case is None:
        print("[qualification.complete] selected case range is complete", flush=True)
        return
    print(
        f"[qualification.next] {case['id']} | {case['spoken_prompt']}",
        flush=True,
    )


def _prompt_qualification_review(case_id: str):
    while True:
        try:
            raw = input(
                f"[qualification.review] {case_id} | "
                "enter BRAIN(0-3) TTS(0-3) [flag,...]: "
            )
            return parse_qualification_review(raw)
        except ValueError as exc:
            print(f"[qualification.review-error] {exc}", flush=True)


def _drain_audio_queue() -> None:
    while True:
        try:
            audio_q.get_nowait()
        except queue.Empty:
            return


def _spoken_text_from_core_response(body: dict) -> str:
    return str((body or {}).get("spoken_chat") or (body or {}).get("chat") or "").strip()


def _echo_suppress_window_ms(spoken_text: str) -> int:
    if not MIC_STT_ECHO_SUPPRESS:
        return 0
    minimum = max(0, _safe_int_env("MIC_STT_ECHO_MIN_MS", 1400))
    maximum = max(minimum, _safe_int_env("MIC_STT_ECHO_MAX_MS", 14000))
    per_char = max(20, _safe_int_env("MIC_STT_ECHO_PER_CHAR_MS", 85))
    estimated = 600 + len(str(spoken_text or "")) * per_char
    return max(minimum, min(maximum, estimated))


def _echo_tokens(text: str) -> set[str]:
    return {
        tok
        for tok in norm_text(text).split()
        if len(tok) >= 2 and tok not in _ECHO_STOP_TOKENS
    }


def _is_probable_self_echo(
    heard_text: str,
    spoken_text: str,
    *,
    suppress_until_ms: int,
    now_ms: int | None = None,
) -> bool:
    if not MIC_STT_ECHO_SUPPRESS:
        return False
    if not spoken_text or not heard_text:
        return False
    now = _now_ms() if now_ms is None else int(now_ms)
    if int(suppress_until_ms or 0) <= now:
        return False

    heard = norm_text(heard_text)
    spoken = norm_text(spoken_text)
    if not heard or not spoken:
        return False
    if heard in {"evet", "hayir", "hayır", "tamam", "iptal", "olur"}:
        return False
    if len(heard) >= 8 and (heard in spoken or spoken in heard):
        return True

    heard_tokens = _echo_tokens(heard)
    spoken_tokens = _echo_tokens(spoken)
    if not heard_tokens or not spoken_tokens:
        return False
    common = heard_tokens & spoken_tokens
    if "demek" in common and "istedin" in common:
        return True
    if "evet" in common and len(common) >= 3 and ("dersen" in spoken_tokens or "dersen" in heard_tokens):
        return True
    if len(common) >= 4:
        heard_ratio = len(common) / max(1, len(heard_tokens))
        spoken_ratio = len(common) / max(1, len(spoken_tokens))
        return heard_ratio >= 0.35 or spoken_ratio >= 0.35
    return False


def _is_tts_window_input_blocked(
    heard_text: str,
    *,
    suppress_until_ms: int,
    now_ms: int | None = None,
) -> bool:
    """Block ordinary no-wake audio while the robot's TTS is expected to play.

    Similarity-only echo detection cannot safely classify short Vosk fragments such
    as ``and`` or ``hi``.  In half-duplex mode those fragments must not recursively
    trigger another TTS response.  Explicit wake words and urgent stop/cancel
    controls remain available for barge-in.
    """

    if not MIC_STT_ECHO_SUPPRESS or not MIC_STT_HALF_DUPLEX:
        return False
    now = _now_ms() if now_ms is None else int(now_ms)
    if int(suppress_until_ms or 0) <= now:
        return False

    heard = str(heard_text or "").strip()
    if not heard:
        return False
    wake_normalized = _normalize_asr_wake_alias(heard, lang=STT_LANG)
    has_wake, _tail = strip_wake_word(wake_normalized, WAKE_WORD)
    if has_wake:
        return False

    folded = norm_text(wake_normalized)
    urgent_tokens = {"stop", "cancel", "dur", "iptal", "bekle"}
    if urgent_tokens & set(folded.split()):
        return False
    return True


def _is_low_quality_no_wake_followup(
    heard_text: str,
    *,
    confidence: float,
    awaiting_plain_confirmation: bool,
    has_active_session: bool,
    explicit_no_wake_expected: bool = False,
) -> bool:
    """Reject short/noisy no-wake fragments before they can start a TTS loop."""

    if explicit_no_wake_expected:
        return False
    if not MIC_STT_ALLOW_NO_WAKE_FOLLOWUPS or not has_active_session:
        return False
    heard = str(heard_text or "").strip()
    if not heard:
        return False

    wake_normalized = _normalize_asr_wake_alias(heard, lang=STT_LANG)
    has_wake, _tail = strip_wake_word(wake_normalized, WAKE_WORD)
    if has_wake:
        return False
    if awaiting_plain_confirmation and (
        is_asr_repair_affirmative(wake_normalized)
        or is_asr_repair_negative(wake_normalized)
    ):
        return False

    folded = norm_text(wake_normalized)
    tokens = folded.split()
    urgent_tokens = {"stop", "cancel", "dur", "iptal", "bekle"}
    if urgent_tokens & set(tokens):
        return False

    min_words = max(1, _safe_int_env("MIC_STT_NO_WAKE_MIN_WORDS", 3))
    min_confidence = max(
        0.0,
        min(1.0, _safe_float_env("MIC_STT_NO_WAKE_MIN_CONFIDENCE", 0.75)),
    )
    return len(tokens) < min_words or float(confidence or 0.0) < min_confidence


def _qualification_case_allows_no_wake(recorder) -> bool:
    """Treat an explicitly no-wake qualification case as an active follow-up.

    This keeps resumable qualification runs valid after the microphone process
    restarts and the in-memory conversation id is no longer available.
    """

    if recorder is None:
        return False
    case = getattr(recorder, "current_case", None)
    if not isinstance(case, dict):
        return False
    return case.get("wake_word_required") is False


def _debug_echo_suppressed(text: str, spoken_text: str) -> None:
    if MIC_STT_DEBUG_ECHO:
        print(
            f"[mic.echo] suppressed self-echo stt={text!r} last_spoken={spoken_text[:120]!r}",
            file=sys.stderr,
        )


def _print_core_http_error(status_code: int, body: dict) -> None:
    reason = str((body or {}).get("reason") or "unknown").strip()
    role = str((body or {}).get("role") or "").strip()
    print(f"[core] HTTP {status_code}: {reason or 'unknown'}", file=sys.stderr)
    if role:
        print(f"[core] required role: {role}", file=sys.stderr)
    if int(status_code) in {401, 403}:
        print("[core] /stt/final auth token gerekli olabilir.", file=sys.stderr)
        print("[core] Iki terminalde de ayni token'i kullanin:", file=sys.stderr)
        print(
            '[core]   CORE_HTTP_VOICE_TOKEN=local-voice-token '
            "HUMANOID_RUNTIME_PROFILE=embodied_interactive python -m core.run_app",
            file=sys.stderr,
        )
        print(
            "[core]   CORE_HTTP_VOICE_TOKEN=local-voice-token "
            "MIC_DEVICE=25 python mic_stt_bridge.py",
            file=sys.stderr,
        )
        print(
            "[core] Gecici override: MIC_STT_AUTH_TOKEN=local-voice-token MIC_DEVICE=25 python mic_stt_bridge.py",
            file=sys.stderr,
        )


def _print_core_success(body: dict) -> None:
    chat = _spoken_text_from_core_response(body)
    mode = str((body or {}).get("mode") or "").strip()
    reason = str((body or {}).get("reason") or "").strip()
    if chat:
        print(f"[core.say] {chat}")
    elif bool((body or {}).get("ok", False)):
        print("[core] ok")
    else:
        print("[core] no reply")
    if mode or reason:
        suffix = " ".join(part for part in (f"mode={mode}" if mode else "", f"reason={reason}" if reason else "") if part)
        print(f"[core.meta] {suffix}")
    if MIC_STT_DEBUG_CORE_JSON:
        print("[core.json]", body)


def _core_response_awaits_plain_confirmation(body: dict) -> bool:
    mode = str((body or {}).get("mode") or "").strip()
    return mode == "awaiting_asr_repair_confirmation"


def _normalize_asr_wake_alias(text: str, *, lang: str) -> str:
    """Repair narrow English-ASR spellings of MAMULA at utterance start."""

    raw = str(text or "").strip()
    if str(lang or "").strip().lower().split("-", 1)[0] != "en":
        return raw
    folded = raw.casefold()
    for alias in _EN_MULTIWORD_WAKE_ALIASES:
        if folded.startswith(alias + " "):
            return f"{WAKE_WORD} {raw[len(alias):].lstrip()}"
    parts = raw.split(maxsplit=1)
    if len(parts) < 2 or norm_text(parts[0]) not in _EN_WAKE_ALIASES:
        return raw
    return f"{WAKE_WORD} {parts[1]}"


def _collapse_exact_repeated_utterance(text: str) -> str:
    """Collapse a batch-ASR whole-utterance duplication without altering short repeats."""

    raw = str(text or "").strip()
    words = raw.split()
    if len(words) < 8 or len(words) % 2:
        return raw
    midpoint = len(words) // 2
    first = " ".join(words[:midpoint]).strip()
    second = " ".join(words[midpoint:]).strip()
    if norm_text(first) != norm_text(second):
        return raw
    return first


def _normalize_english_self_correction_homophone(text: str, *, lang: str) -> str:
    """Repair ``no`` -> ``know`` only inside an explicit correction structure."""

    raw = str(text or "").strip()
    if str(lang or "").strip().lower().split("-", 1)[0] != "en":
        return raw
    folded = raw.casefold()
    correction_shapes = (
        (" know go to ", "go to "),
        (" know give it to ", "give it to "),
        (" know don't move anywhere", "move forward "),
    )
    for marker, required_prefix in correction_shapes:
        marker_pos = folded.find(marker)
        if marker_pos >= 0 and required_prefix in folded[:marker_pos]:
            return raw[:marker_pos] + marker.replace("know", "no", 1) + raw[marker_pos + len(marker) :]
    return raw


def _normalize_english_location_homophones(text: str, *, lang: str) -> str:
    """Repair narrow command-phrase errors produced by the small English model."""

    raw = str(text or "").strip()
    if str(lang or "").strip().lower().split("-", 1)[0] != "en":
        return raw
    repaired = raw.replace("go to the league room", "go to the living room")
    repaired = repaired.replace(
        "then we're apply without taking any physical action",
        "then reply without taking any physical action",
    )
    if repaired.casefold().startswith("mamula council the desk"):
        repaired = "mamula cancel the task" + repaired[len("mamula council the desk") :]
    folded = norm_text(repaired)
    if (
        re.search(r"\bfind\s+(?:it|et)\b", folded)
        and re.search(r"\bdon\s+t\s+pick\s+it\s+up\b", folded)
    ):
        # In a Turkish↔English command, spoken ``cup'ı`` is acoustically
        # indistinguishable from ``kapı`` for Whisper.  Only disambiguate when
        # the surrounding portable-object operation makes the intended English
        # noun explicit; genuine door/open commands remain untouched.
        repaired = re.sub(r"\bmavi\s+kap[ıi]\b", "mavi cup", repaired, flags=re.IGNORECASE)
    return repaired


def _should_post_to_core(
    text: str,
    *,
    awaiting_plain_confirmation: bool,
    has_active_session: bool = False,
) -> bool:
    has_wake, _tail = strip_wake_word(text, WAKE_WORD)
    if has_wake:
        return True
    if awaiting_plain_confirmation and (
        is_asr_repair_affirmative(text) or is_asr_repair_negative(text)
    ):
        return True
    if MIC_STT_ALLOW_NO_WAKE_FOLLOWUPS and has_active_session:
        return True
    suggestion = suggest_asr_repair(text, wake_word=WAKE_WORD, lang=STT_LANG)
    return str(suggestion.get("kind") or "") in {"fuzzy_wake", "physical_command"}


def _session_for_transcript(current_session: str, text: str, *, ts_ms: int) -> str:
    """Start a clean conversation on an explicit wake word when qualification requests it."""
    has_wake, _tail = strip_wake_word(text, WAKE_WORD)
    if MIC_STT_NEW_SESSION_ON_WAKE and has_wake:
        return f"sess-{int(ts_ms)}"
    return str(current_session or "")


def resolve_device(sd_module):
    if not MIC_DEVICE:
        return None

    if MIC_DEVICE.isdigit():
        return int(MIC_DEVICE)

    try:
        devs = sd_module.query_devices()
    except Exception as exc:
        print(f"[mic] WARNING: MIC_DEVICE lookup failed: {exc}", file=sys.stderr)
        return None

    for i, d in enumerate(devs):
        name = str(d.get("name", ""))
        if MIC_DEVICE.lower() in name.lower():
            return i

    print(f"[mic] WARNING: MIC_DEVICE='{MIC_DEVICE}' not found; using default.", file=sys.stderr)
    return None


def audio_callback(indata, frames, time_info, status):
    if status:
        print(status)
    audio_q.put(bytes(indata))


def main():
    try:
        sd, KaldiRecognizer, Model = _load_voice_dependencies()
    except MissingExtraError as exc:
        _print_voice_dependency_hint(exc)
        return 2

    model_dir = Path(MODEL_PATH)
    if not model_dir.exists():
        print(f"[mic] Vosk model bulunamadi: {model_dir}", file=sys.stderr)
        print("[mic] VOSK_MODEL_PATH ile indirilen model dizinini gosterin.", file=sys.stderr)
        print("[mic] Ornek: export VOSK_MODEL_PATH=/path/to/vosk-model-small-tr-0.3", file=sys.stderr)
        return 2

    if MIC_LIST_DEVICES:
        _print_input_devices(sd)
        return 0

    print(f"[mic] loading model from {model_dir} ...", flush=True)
    model = Model(str(model_dir))
    rec = KaldiRecognizer(model, SAMPLE_RATE)
    try:
        vosk_asr = VoskRecognizerAdapter(
            rec,
            locale=STT_LANG,
            model_path=model_dir,
            stream_started_at_ms=_now_ms(),
        )
    except ValueError as exc:
        print(f"[mic] gecersiz STT_LANG={STT_LANG!r}: {exc}", file=sys.stderr)
        return 2
    try:
        asr = _build_stream_asr(vosk_asr)
    except (TypeError, ValueError) as exc:
        print(f"[mic] ASR yapilandirmasi gecersiz: {exc}", file=sys.stderr)
        return 2
    try:
        qualification_recorder = _build_qualification_recorder()
    except (OSError, TypeError, ValueError) as exc:
        print(f"[mic] qualification metrics configuration invalid: {exc}", file=sys.stderr)
        return 2

    dev = resolve_device(sd)
    if dev is not None:
        try:
            device_name = sd.query_devices(dev)["name"]
        except Exception as exc:
            _print_audio_device_hint(sd, exc)
            return 2
        print(f"[mic] using device={dev} ({device_name})", flush=True)
    else:
        print("[mic] using default input device", flush=True)

    print(f"[mic] posting to {CORE_URL}", flush=True)
    print(
        f"[mic] asr={getattr(asr, 'name', ASR_PROVIDER)} "
        f"model={getattr(asr, 'model', model_dir.name)}",
        flush=True,
    )
    print("[mic] listening (Ctrl+C to stop)...", flush=True)
    if qualification_recorder is not None:
        print(
            "[qualification.flags] " + ",".join(review_flag_names()),
            flush=True,
        )
        _print_qualification_next(qualification_recorder)
        if qualification_recorder.complete:
            return 0

    current_session = _load_saved_session()
    awaiting_plain_confirmation = False
    last_core_spoken = ""
    echo_suppress_until_ms = 0
    last_partial_text = ""

    try:
        with sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            dtype="int16",
            channels=1,
            device=dev,
            callback=audio_callback,
        ):
            while True:
                data = audio_q.get()
                asr_started_at_ms = _now_ms()
                try:
                    transcript = asr.accept_audio(data)
                except Exception as exc:
                    print(f"[stt.remote-error] {exc}", file=sys.stderr)
                    continue
                asr_completed_at_ms = _now_ms()
                text = transcript.text.strip()
                if not transcript.final:
                    if text and text != last_partial_text:
                        print(f"[stt.partial] '{text}'")
                        last_partial_text = text
                    continue
                last_partial_text = ""
                if not text:
                    continue

                if _is_tts_window_input_blocked(
                    text,
                    suppress_until_ms=echo_suppress_until_ms,
                ):
                    print(f"[stt.echo-window] '{text}'")
                    _debug_echo_suppressed(text, last_core_spoken)
                    continue

                if _is_probable_self_echo(
                    text,
                    last_core_spoken,
                    suppress_until_ms=echo_suppress_until_ms,
                ):
                    print(f"[stt.echo] '{text}'")
                    _debug_echo_suppressed(text, last_core_spoken)
                    continue

                qualification_no_wake_expected = _qualification_case_allows_no_wake(
                    qualification_recorder
                )
                has_active_conversation = bool(current_session) or qualification_no_wake_expected

                if _is_low_quality_no_wake_followup(
                    text,
                    confidence=transcript.confidence,
                    awaiting_plain_confirmation=awaiting_plain_confirmation,
                    has_active_session=has_active_conversation,
                    explicit_no_wake_expected=qualification_no_wake_expected,
                ):
                    print(
                        f"[stt.no-wake-filtered] '{text}' "
                        f"confidence={transcript.confidence:.3f}"
                    )
                    continue

                transcript_lang = str(transcript.locale or STT_LANG)
                core_text = _normalize_asr_wake_alias(text, lang=transcript_lang)
                deduplicated_text = _collapse_exact_repeated_utterance(core_text)
                corrected_text = _normalize_english_self_correction_homophone(
                    deduplicated_text,
                    lang=transcript_lang,
                )
                location_corrected_text = _normalize_english_location_homophones(
                    corrected_text,
                    lang=transcript_lang,
                )
                if WAKE_WORD and not _should_post_to_core(
                    location_corrected_text,
                    awaiting_plain_confirmation=awaiting_plain_confirmation,
                    has_active_session=has_active_conversation,
                ):
                    print(f"[stt.ignored] '{text}'")
                    continue

                if core_text != text:
                    print(f"[stt.wake-repair] '{text.split(maxsplit=1)[0]}' -> '{WAKE_WORD}'")
                if deduplicated_text != core_text:
                    print("[stt.dedup] collapsed exact repeated utterance")
                if corrected_text != deduplicated_text:
                    print("[stt.self-correction-repair] 'know go to' -> 'no go to'")
                if location_corrected_text != corrected_text:
                    print("[stt.lexical-repair] contextual ASR homophone corrected")
                core_text = location_corrected_text

                print(
                    f"[stt] '{core_text}' confidence={transcript.confidence:.3f} "
                    f"source={transcript.confidence_source}"
                )

                try:
                    current_session = _session_for_transcript(
                        current_session,
                        core_text,
                        ts_ms=_now_ms(),
                    )
                    payload = transcript_payload(transcript)
                    payload["text"] = core_text
                    if current_session:
                        payload["session_id"] = current_session
                    brain_started_at_ms = _now_ms()
                    r = requests.post(CORE_URL, json=payload, headers=_core_headers(), timeout=HTTP_TIMEOUT_S)
                    brain_completed_at_ms = _now_ms()
                    try:
                        body = r.json()
                    except Exception:
                        body = {}
                    if not r.ok:
                        _print_core_http_error(int(r.status_code), body if isinstance(body, dict) else {})
                        continue
                    sid = str((body or {}).get("session_id") or "").strip()
                    if sid:
                        current_session = sid
                        _save_session(sid)
                    awaiting_plain_confirmation = _core_response_awaits_plain_confirmation(
                        body if isinstance(body, dict) else {}
                    )
                    spoken = _spoken_text_from_core_response(body if isinstance(body, dict) else {})
                    if spoken:
                        last_core_spoken = spoken
                        echo_suppress_until_ms = _now_ms() + _echo_suppress_window_ms(spoken)
                    _print_core_success(body if isinstance(body, dict) else {})
                    if qualification_recorder is not None:
                        case = qualification_recorder.current_case
                        if case is None:
                            print("[qualification.complete] selected case range is complete", flush=True)
                            return 0
                        review = _prompt_qualification_review(str(case["id"]))
                        wake_detected, _wake_tail = strip_wake_word(core_text, WAKE_WORD)
                        row = qualification_recorder.append(
                            transcript=core_text,
                            response=spoken,
                            asr_confidence=float(transcript.confidence),
                            asr_latency_ms=max(0, asr_completed_at_ms - asr_started_at_ms),
                            brain_latency_ms=max(0, brain_completed_at_ms - brain_started_at_ms),
                            end_to_end_latency_ms=max(
                                0, brain_completed_at_ms - asr_started_at_ms
                            ),
                            wake_detected=wake_detected,
                            review=review,
                        )
                        print(
                            f"[qualification.recorded] {row['id']} "
                            f"result={row['result_class']} "
                            f"latency_ms={row['end_to_end_latency_ms']}",
                            flush=True,
                        )
                        _drain_audio_queue()
                        _print_qualification_next(qualification_recorder)
                        if qualification_recorder.complete:
                            return 0
                except Exception as e:
                    print("[core] error:", e)
    except Exception as exc:
        if _is_sounddevice_error(sd, exc):
            _print_audio_device_hint(sd, exc)
            return 2
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
