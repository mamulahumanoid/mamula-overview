# Tanılama, günlük ve replay — Aşama 7

Saha üzerinde **neden böyle davrandı** sorusunun yanıtı, OS seviyesinde **iz**, **günlük** ve **yeniden oynatma** olmadan çıkmaz. Bu belge Aşama 7 kapsamını ve depodaki karşılıkları tanımlar.

**İlgili:** `topic_atlas.md`, `message_contract_v1.md`, `lifecycle_manager_stage6.md`, `hardware_abstraction_layer_v1.md`, `real_time_control_core_stage5.md`.

---

## Hedef yetenekler

| Yetenek | Amaç | Repo işaretçisi / durum |
|--------|------|-------------------------|
| **Event timeline** | Zaman sırasına göre olaylar (bus + HTTP) | `EventRecorderModule` → `logs/session_*.jsonl`; birleşik zaman çizgisi için `mamula.observability.timeline_segment.v1` (sözleşme) |
| **Task trace** | Görev / adım izi | `action.lifecycle`, `action.result`, `executive.action_*`, task_id ile JSONL filtreleme |
| **Safety trace** | Kapı, risk, estop, policy | `action_router.risk_blocked`, `controller.safety_latched`, `hardware.health`, audit log |
| **LLM trace** | Model çağrıları ve özet karar | `reasoning_trace_aggregator` + SQLite (`HUMANOID_REASONING_TRACE_DB`), LLM topic’leri profil bazlı |
| **Control latency trace** | Native köprü / komut gecikmesi | `control.core.reply` `core_diagnostics`, `cpp_control_route_module`, Aşama 5 |
| **Sensor health trace** | IMU, telemetri yaşı, bayatlık | `robot.diagnostics.status`, `lifecycle.status`, ops `/ops/hardware_telemetry/data` |
| **Driver fault trace** | HAL / sürücü hataları | HAL `fault_code`, `hardware.telemetry` `faults`, `aggregate_hal_snapshot` |
| **Episode recorder** | Oturum kaydı | `EventRecorderModule` (tam bus); daraltılmış: `MotionTraceModule`, `JointTraceModule` |
| **Replay tool** | Kayıttan senaryo / smoke | `mamula replay logs/session_2026_05_16.jsonl` (forensic + karar zaman çizelgesi); `mamula replay session <path> --bus` → EventBus; bkz. [OBSERVABILITY_REPLAY.md](../../docs/OBSERVABILITY_REPLAY.md) |
| **Control audit** | Sim/HIL/real komut izi | `control_audit_recorder` → `logs/session_*.jsonl` (`mamula.control_audit.v1`) |
| **Failure snapshot** | Arıza anı durumu | `write_failure_snapshot()` (`core/utils/failure_snapshot.py`): `MAMULA_FAILURE_SNAPSHOT_ENABLED=1`, `MAMULA_FAILURE_DIR`. Tetik: `action_router.risk_blocked`, `FailureSnapshotModule` → `controller.safety_latched` |

---

## CLI (`mamula`)

Paket giriş noktası: `mamula` → `core.tools.mamula_cli:main`.

| Komut | Açıklama |
|-------|----------|
| `mamula doctor` | Python sürümü, `CONTROL_CORE_BRIDGE_BIN`, audit / trace yolları, temel çevre |
| `mamula diagnostics` | `CORE_HTTP_BASE_URL` (varsayılan `http://127.0.0.1:5055`) üzerinden ops telemetry özeti — token için `CORE_OPS_TOKEN` veya `Authorization` |
| `mamula logs <safety\|llm\|control\|sensor\|driver\|all>` | `MAMULA_LOG_DIR` altındaki `session_*.jsonl` / `motion_trace_*.jsonl` içinde anahtar kelime süzme |
| `mamula trace task <trace_id>` | `HUMANOID_REASONING_TRACE_DB` SQLite’tan reasoning adımları |
| `mamula replay last-failure` | `MAMULA_FAILURE_DIR` (varsayılan `data/failure_snapshots`) en yeni anlık görüntü özeti |
| `mamula replay session <path>` | Oturum JSONL → süreç içi `EventBus` (canlı modüller aboneyse işlenir); `--dry-run`, `--speed`, `--topic-prefix`, `--start-ms` |

Tam replay motoru ve birleşik timeline deposu **yol haritası**dır; CLI önce operasyonel keşfi hızlandırır.

---

## Ortam değişkenleri (özet)

| Değişken | Anlam |
|----------|--------|
| `MAMULA_LOG_DIR` | JSONL oturum dizini (varsayılan `./logs`) |
| `HUMANOID_REASONING_TRACE_DB` | Reasoning trace SQLite |
| `CORE_HTTP_AUDIT_LOG_PATH` | HTTP / ops audit JSONL (`audit.py`) |
| `CORE_HTTP_BASE_URL` | `mamula diagnostics` hedefi |
| `CORE_OPS_TOKEN` | Bearer token (ops yetkisi varsa) |
| `MAMULA_FAILURE_DIR` | Failure snapshot dosya kökü |

---

## Aşama 7 kabul ölçütleri

- [x] Kritik güvenlik ve görev olayları kayda bağlanabilir (JSONL veya SQLite).
- [x] Tek trace_id veya task_id ile zincir takip edilebilir (`mamula trace task`, JSONL filtreleri).
- [x] Operatör tek komutla sağlık HTTP özeti ve yerel doctor çıktısı alır (`mamula diagnostics`, `mamula doctor`).

Bu belge canlıdır; replay binary formatı ve timeline birleştirme üretim ihtiyacına göre genişler.
