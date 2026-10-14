# Aşama 1 — Güvenli gateway ve runtime sertleştirme

Bu belge, “robot OS” iddiası için **minimum** gateway hedeflerini ve repodaki karşılıklarını özetler.

## Hedefler

1. **Doğrulanmamış payload EventBus’a gitmesin**  
   HTTP girişleri `schemas` ile tip/sınır doğrulamasından geçer; perception/voice/LLM gövdeleri şema ile temizlenir. Voice STT: `voice_routes` → `schemas.validate_stt_final_payload` → `handle_stt_final`.

2. **Fiziksel komutlar auth + wake + safety zinciri olmadan çalışmasın**  
   - **Auth:** `auth.guard_request` (rol `voice`), token/policy: `core/adapters/auth.py`, `auth_policy.py`. Üretimde `CORE_HTTP_REQUIRE_AUTH=1` ve/veya policy dosyasında `auth_required: true`.  
   - **Wake / risk kapısı:** `voice_command_service.handle_stt_final` içinde wake ve L3/L4 operasyonel kapı.  
   - **Audit izi:** fiziksel görev yayınında `audit.log_event(..., category=security.voice, action=voice.physical_task_dispatch)` (`voice_routes`).

3. **Config / safety değişiklikleri audit’te**  
   - HTTP auth policy atomik yazım: `secure_config.save_runtime_http_auth_policy` → `audit.log_event` (`security.config`, `http_auth_policy_put`).  
   - Safety uçları: `audit.log_change` ile `category=security.safety` (`safety_routes`).  
   - Audit dosyası: `CORE_HTTP_AUDIT_LOG_PATH` veya varsayılan `data/runtime/http_ops_audit.jsonl`.

## Modül haritası

| Modül | Rol |
|--------|-----|
| `core/adapters/auth.py` | Bearer / X-Auth-Token, rol, local_only |
| `core/adapters/rate_limit.py` | `CORE_HTTP_RATE_LIMIT=1`, scope: voice, ops, perception, safety |
| `core/adapters/schemas.py` | JSON doğrulama ve sanitization girişleri |
| `core/adapters/audit.py` | JSONL audit; `log_change` isteğe bağlı `category` |
| `core/adapters/secure_config.py` | Hassas runtime config atomik yazım + audit |
| `core/adapters/auth_policy.py` | Policy yükleme; `invalidate_http_auth_policy_cache` |

## Operasyon notları

- Policy güncelleme: `POST /ops/http_auth_policy` (ops rolü + local_only varsayılan); gövde `schemas.validate_http_auth_policy_put_payload` ile sınırlı anahtarlar.  
- Üretim checklist: `CORE_HTTP_REQUIRE_AUTH`, `CORE_HTTP_RATE_LIMIT`, güçlü token haritası, TLS terminasyonu (reverse proxy), `MAX_CONTENT_LENGTH` (`CORE_HTTP_MAX_BODY_BYTES`).

İlgili: `architecture_index.md`.
