# C++ Low-Level Migration Plan v1

Bu doküman, mevcut Python ağırlıklı kontrol/hardware katmanından C++ çekirdeğe geçiş için
başlangıç planını tanımlar.

**İlgili:** Python ile gerçek zamanlı katmanın sorumluluk ayrımı için `control_plane_python_vs_native.md`; belge haritası için `architecture_index.md`.

## Hedef

- Deterministic timing ve düşük jitter
- Daha düşük control-loop gecikmesi
- Hardware I/O tarafında daha öngörülebilir davranış
- Python katmanını task/planning/orchestration tarafında korumak

## Mimari sınır

### C++ tarafına taşınacak

- Low-level motor komut pipeline
- Real-time control loop scheduler
- Whole-body IK/ID/QP çekirdekleri
- Sensor fusion ve state-estimation çekirdeği
- Hardware transport/protocol (CAN/serial/EtherCAT vb.)

### Python tarafında kalacak

- Task planner
- World model
- Action routing / executive orchestration
- Simulation harness ve test orchestration

## Faz planı

### Phase-1 (bu commit)

- `native/control_core/` iskeleti eklendi
- CMake build tanımı eklendi
- Minimal C++ `ControlCore` API tanımlandı
- stdin/stdout bridge executable (`control_core_bridge`) eklendi

Bu fazda amaç performans değil, entegrasyon yüzeyini sabitlemektir.

### Phase-2

- Python tarafında bridge adapter modülü (subprocess/IPC) üret
- `executive` ve/veya `hardware bridge` tarafında feature flag ile seçilebilir hale getir
- Health/status ve hata sözleşmesini netleştir

Durum:

- `core/modules/robot/cpp_control_bridge_module.py` eklendi.
- `core/modules/robot/cpp_control_route_module.py` eklendi (actuator bundle -> control.core.command).
- C++ bridge (`native/control_core/src/main.cpp`) request contract doğrulaması command-bazlı zorunlu payload key kontrolü içerir (`invalid_payload_shape` + `required_key`).
- `ControlCore::handle` artık command-family bazlı deterministic `status` üretir (`accepted.scheduler`, `accepted.estimator`, `accepted.qp_solver`, vb.); çekirdek reddinde `error_code=control_core_rejected` döner.
- C++ reply `result_payload.core_diagnostics` alanı içerir (`command_family`, `accepted`, `handler_status`).
- `scheduler_tick` için native çekirdek deterministic cycle hesabı üretir ve `core_diagnostics` altında `scheduler_cycle`, `scheduler_nominal_period_ms`, `scheduler_deadline_slack_ms` alanlarını yayınlar.
- `estimate_robot_state` için native fusion-lite sinyal `core_diagnostics` altında `estimator_phase_bucket` ve `estimator_confidence_milli` olarak yayınlanır.
- `solve_real_qp` için native mini QP çözücü (projected gradient) çalışır ve `core_diagnostics` altında `qp_iteration_count`, `qp_residual_milli`, `qp_objective_milli`, `qp_solution_norm_milli` yayınlanır.
- `solve_whole_body_ik` için native kalite sinyali `core_diagnostics` altında `ik_iteration_count`, `ik_pose_error_milli` olarak yayınlanır.
- `solve_whole_body_inverse_dynamics` için native kalite sinyali `core_diagnostics` altında `id_torque_norm_milli`, `id_balance_margin_milli` olarak yayınlanır.
- `solve_whole_body_qp_command` için native kalite sinyali `core_diagnostics` altında `qp_command_saturation_milli`, `qp_command_active_constraints` olarak yayınlanır.
- `resolve_whole_body_task_priority` için native kalite sinyali `core_diagnostics` altında `task_priority_level_count`, `task_priority_top_level` olarak yayınlanır.
- Backend seçimi:
  - `CONTROL_CORE_BACKEND=python|cpp` (varsayılan: `python`)
  - `CONTROL_CORE_BRIDGE_BIN=<path>` (cpp bridge executable yolu)
- Profil wiring:
  - `CONTROL_CORE_ENABLE_BRIDGE=1` ile `s422` ve `s422_light` içinde route+bridge modülleri aktif olur.
  - `CONTROL_CORE_CPP_SHADOW_CORE=1` ile phase-3 çekirdek modüller shadow modda C++ bridge'e mirror edilir:
    - `deterministic_control_scheduler`
    - `state_estimator`
    - `actuator_command_compiler`
    - `task_priority_resolver`
    - `whole_body_qp_controller`
    - `real_qp_solver`
    - `whole_body_inverse_kinematics`
    - `whole_body_inverse_dynamics`
  - `CONTROL_CORE_CPP_PRIMARY_OUTPUT=1` ile C++ candidate çıktısı ana topic'lere promote edilir (guarded rollout).
  - Modül bazlı primary rollout:
    - `CONTROL_CORE_CPP_PRIMARY_COMPILER=1`
    - `CONTROL_CORE_CPP_PRIMARY_ESTIMATOR=1`
    - `CONTROL_CORE_CPP_PRIMARY_SCHEDULER=1`
    - `CONTROL_CORE_CPP_PRIMARY_TASK_PRIORITY=1
    - `CONTROL_CORE_CPP_PRIMARY_QP_CONTROLLER=1``
    - `CONTROL_CORE_CPP_PRIMARY_QP_SOLVER=1`
    - `CONTROL_CORE_CPP_PRIMARY_IK_SOLVER=1`
    - `CONTROL_CORE_CPP_PRIMARY_ID_SOLVER=1`
    - Bu env'ler global `CONTROL_CORE_CPP_PRIMARY_OUTPUT` değerini ilgili modül için override eder.
  - Profile preset rollout (env tanımlı değilse):
    - `s422_light`: `scheduler=true`, `compiler=false`, `estimator=false`
    - `s422`: `scheduler=true`, `compiler=true`, `estimator=false`
    - Merkezi tanım: `core/config/control_core_latency_ab_config.py`
- Topic yüzeyi:
  - yönlendirme giriş: `hardware.actuator_command_bundle`
  - istek: `control.core.command`
  - yanıt: `control.core.reply`
  - latency telemetri: `control.core.latency`
  - latency aggregate: `control.core.latency.metrics` (overall + backend p50/p95/p99)
  - latency sorgu: `control.core.latency.query` -> `control.core.latency.result`
  - A/B rapor: `control.core.latency.ab.report` (python baseline vs cpp candidate)
  - A/B sorgu: `control.core.latency.ab.query` -> `control.core.latency.ab.result`
  - durum sorgu: `control.core.query` -> `control.core.result`

A/B gate threshold ayarları (env):

- `CONTROL_CORE_AB_AVG_MAX_DELTA_MS` (varsayılan `0.0`)
- `CONTROL_CORE_AB_P95_MAX_DELTA_MS` (varsayılan `0.0`)
- `CONTROL_CORE_AB_P99_MAX_DELTA_MS` (varsayılan `0.0`)

Profile preset:

- Profil çözümleme sırası: `CONTROL_CORE_AB_PROFILE` -> `HUMANOID_RUNTIME_PROFILE` -> `CORE_RUNTIME_PROFILE` -> `default`
- Preset eşikleri:
  - `s422_light`: `avg=0.0`, `p95=0.0`, `p99=0.0`
  - `s422`: `avg=1.0`, `p95=2.0`, `p99=3.0`
- Açık env threshold'lar presetleri override eder.

Bu modül şu anda kontrollü entegrasyon için hazırdır; profile otomatik bağlama adımı
Phase-3 öncesinde rollout planına göre yapılmalıdır.

Python tarafında kalacak (bilinçli olarak):

- `world_model`, `task_manager`, `reasoning`, `action_router`
- üst-seviye task/planner/orchestration ve test harness katmanları

### Phase-3

- Control scheduler ve actuator command compiler çekirdeğini C++'a taşı
- Robot physical state için C++ estimator çıkışını contract ile hizala

### Phase-4

- Whole-body solver çekirdeği C++ (IK/ID/QP) + performans tuning
- HIL regresyonları ve safety gate doğrulaması

### Phase-5 — Canonical Native Control API

Canonical C ABI (`native/control_core/include/control_core/native_control_api.h`)
Python contract types (`core/modules/robot/native_control_types.py`)
ve `NativeControlBridge` modülü (`core/modules/robot/native_control_bridge.py`)
eklendi.

Amaç: Python ↔ native sınırını tek, stabil bir API ile netleştirmek.

Native API fonksiyonları:

| Fonksiyon | Yön | Açıklama |
|---|---|---|
| `mamula_cc_init(config)` | Python → native | Kontrol çekirdeğini başlat |
| `mamula_cc_destroy(handle)` | Python → native | Yıkım |
| `mamula_cc_update_telemetry(handle, frame)` | Python → native | Sensör verisi gönder |
| `mamula_cc_set_mode(handle, mode)` | Python → native | Kontrol modunu değiştir |
| `mamula_cc_submit_motion_goal(handle, goal)` | Python → native | Hareket hedefi gönder |
| `mamula_cc_step_control(handle, time_ns)` | Python → native | Bir kontrol adımı çalıştır |
| `mamula_cc_get_command_frame(handle, out)` | native → Python | Joint komut frame'i oku |
| `mamula_cc_get_status(handle, out)` | native → Python | Tam durum/hata/estimator oku |
| `mamula_cc_safe_stop(handle, reason)` | Python → native | Öncelikli güvenli durma |

Python'dan gönderilen hareket hedefleri (`MotionGoalType`):

- `STAND`, `HOLD_POSTURE`, `WALK_VELOCITY`, `TURN`, `REACH_TARGET`, `STOP`, `RECOVER`

Python'un native'den aldığı veriler (`ControlStatus`):

- `mode`, `hardware_state`, `stability_margin`, `center_of_mass`, `zero_moment_point`
- `estimator_state` (base_position, base_orientation, base_velocity, confidence)
- `deadline_miss_count`, `worst_case_step_ns`, `average_step_ns`
- `faults`, `active_goal_id`, `goal_achieved`

C ABI v3 servo policy alanları:

- Joint-bazlı `joint_servo_kp`, `joint_servo_kd`
- Joint-bazlı `joint_acceleration_limits`, `joint_jerk_limits`, `joint_torque_rate_limits`
- Contact-aware impedance için `contact_stance_impedance_scale`, `contact_swing_impedance_scale`
- Native safety için `fall_tilt_limit_rad`, `telemetry_watchdog_cycles`

`mamula_cc_step_control` artık stateful `q_cmd/v_cmd/a_cmd/tau_cmd` servo state'i taşır; hedefler pozisyon/hız/ivme/jerk limitlerinden geçer, effort çıkışı torque-rate limitlidir. Telemetry watchdog veya süresi geçmiş `deadline_ns` içeren aktif goal native safe-stop'a geçer.

Backend seçimi: `NATIVE_CONTROL_BACKEND=sim|subprocess|ctypes` (varsayılan: `sim`).

Bus topic yüzeyi:

| Topic | Yön |
|---|---|
| `native_control.goal` | Python → bridge |
| `native_control.mode` | Python → bridge |
| `native_control.telemetry` | Python → bridge |
| `native_control.safe_stop` | Python → bridge |
| `native_control.query` | Python → bridge |
| `native_control.status` | bridge → Python |
| `native_control.command_frame` | bridge → Python |
| `native_control.result` | bridge → Python |
| `native_control.safe_stop_ack` | bridge → Python |
| `native_control.error` | bridge → Python |

## Başarı metrikleri (KPI)

- Loop period jitter (p95/p99)
- End-to-end command latency
- Command drop/timeout oranı
- Safety watchdog false-positive / false-negative oranı
- HIL senaryolarında stabilize olma süresi

## Riskler ve önlem

- **Risk:** Python ve C++ state drift  
  **Önlem:** Tek kanonik contract (`robot.physical_state`) + bridge seviyesinde schema validation

- **Risk:** Debug zorluğu artışı  
  **Önlem:** Bridge log formatı ve deterministik replay akışı

- **Risk:** Kademeli geçişte iki farklı yürütüm yolu  
  **Önlem:** Feature flag + A/B test + rollback planı

## Build (Phase-1)

```bash
cmake -S native/control_core -B native/control_core/build
cmake --build native/control_core/build --config Release
```

Çıktı:
- static lib: `control_core`
- executable: `control_core_bridge`

## Doğrulama (standart komut)

```bash
python core/scripts/run_phase3_validation.py
```

Not: Native bridge binary yoksa `test_cpp_control_bridge_native_smoke.py` testleri `skip` olur; diğer phase3 doğrulamaları çalışmaya devam eder.

Native build ile birlikte doğrulama:

```bash
python core/scripts/run_phase3_validation.py --build-native
```

Not: `cmake` kurulu değilse script build adımını skip eder ve testleri çalıştırır.

Metrics exporter doğrulamasını dahil etmek için:

```bash
python core/scripts/run_phase3_validation.py --check-metrics-exporter
```

Validation sonrası evidence bundle toplamak için:

```bash
python core/scripts/run_phase3_validation.py --check-metrics-exporter --collect-evidence --evidence-out-dir logs/phase3_evidence --update-evidence-drafts
```

Validation + evidence sonrası closure readiness kontrolü:

```bash
python core/scripts/run_phase3_validation.py --check-metrics-exporter --collect-evidence --evidence-out-dir logs/phase3_evidence --update-evidence-drafts --check-closure-readiness
```

Validation akışına hardware evidence dahil etmek için:

```bash
python core/scripts/run_phase3_validation.py --check-metrics-exporter --collect-evidence --evidence-out-dir logs/phase3_evidence --update-evidence-drafts --with-hardware-evidence --hardware-root-dir data/hardware --check-closure-readiness
```

Release-gate strict doğrulama:

```bash
python core/scripts/run_phase3_validation.py --strict
```

Not: Strict modda native bridge binary yoksa script pytest'e geçmeden erken aşamada `fail (exit 2)` olur ve çözüm adımı önerir.

CI için önerilen release gate komutu:

```bash
python core/scripts/run_phase3_validation.py --build-native --strict --check-metrics-exporter
```

GitHub Actions workflow notu:

- Workflow: `.github/workflows/phase3-strict-gate.yml`
- Önce `phase3-metrics-fast` job'ı exporter testlerini hızlı doğrulama olarak çalıştırır:
  - `core/tests/test_export_phase3_metrics.py`
  - `core/tests/test_run_phase3_metrics_stack.py`
- `phase3-metrics-fast` sonunda smoke event + metrics çıktı artifact'ı yüklenir (`phase3-metrics-fast-evidence`).
- Sonra `phase3-strict` job'ı (`needs: phase3-metrics-fast`) Linux + Windows üzerinde strict gate + evidence collection komutunu çalıştırır.
- Strict job sonunda `logs/phase3_evidence_ci` artifact olarak yüklenir (`phase3-evidence-<os>`).
- `phase3-closure-readiness-report` job'ı non-blocking (`continue-on-error`) olarak closure readiness raporu üretir ve artifact yükler (`phase3-closure-readiness-report`).
- CI evidence toplama akışında hardware kanıtı da dahil edilir (`--with-hardware-evidence --hardware-root-dir data/hardware`).
- Closure readiness job summary'sine manifest özeti (`file_count`, `checks_count`, `closure_overall_ready`, required evidence files) eklenir.

Strict mode CI recipe (binary path override):

```bash
CONTROL_CORE_BRIDGE_BIN=/workspace/native/control_core/build/control_core_bridge \
python core/scripts/run_phase3_validation.py --strict
```

Not: `--build-native --strict` birlikte kullanıldığında `cmake` bulunamazsa build adımı strict gereği fail olur; skip edilmez.

Native smoke kapsamı: desteklenen tüm bridge komutları için (`compile_actuator_bundle`, `estimate_robot_state`, `scheduler_tick`, `resolve_whole_body_task_priority`, `solve_whole_body_qp_command`, `solve_real_qp`, `solve_whole_body_ik`, `solve_whole_body_inverse_dynamics`, `idle`) command/payload contract doğrulaması içerir.



- `control.core.rollout.result` i?inde solver policy g?r?n?r (`qp_solver`, `ik_solver`, `id_solver`).
- Ayn? rollout sonucunda autopilot i?in `autopilot_policy.preset`, `autopilot_policy.effective`, `autopilot_policy.sources` alanlar? da bulunur.
- Ayn? rollout sonucunda `phase3_observability` snapshot'? bulunur (`readiness_summary`, `readiness_gates`, `core_diagnostics`, `decision`).
- `phase3_observability.decision` snapshot'? garantili alan seti ile normalize edilir:
  - `decision`, `confidence`, `recommended_next_action`
  - `severity`, `reason_code`, `runbook_hint`
  - `failed_gates`, `ts_ms`
- Kaynak önceliği: anlık `control.core.phase3.decision` payload'u -> readiness içindeki `decision_preview` fallback'i -> güvenli default alanlar.
- Runtime contract checklist (phase3/rollout/autopilot):

| Topic | Zorunlu alanlar (minimum) | Operasyon amacı |
|---|---|---|
| `control.core.phase3.readiness.result` | `summary`, `gates`, `bridge.core_diagnostics`, `threshold_policy`, `decision_preview` | Gate ve coverage görünürlüğü + decision fallback kaynağı |
| `control.core.phase3.decision` | `decision`, `confidence`, `recommended_next_action`, `severity`, `reason_code`, `runbook_hint`, `failed_gates`, `policy_trace`, `ts_ms` | Go/no-go kararı ve anlık aksiyon yönü |
| `control.core.rollout.result` | `phase3_observability`, `phase3_policy_snapshot`, `health_summary`, `rollout_drift`, `autopilot_policy`, `ts_ms` | Tek payload'ta operasyonel durum özeti |
| `control.core.phase3.autopilot.result` | `enabled`, `allowlist`, `max_solver_risk_score`, `solver_risk_score`, `last_action`, `policy_snapshot`, `ts_ms` | Autopilot runtime policy + son aksiyon görünürlüğü |
| `control.core.phase3.autopilot.action` | `action`, `severity`, `reason_code`, `runbook_hint`, `ts_ms` | Dashboard/alert için event-level alarm sinyali |

Önerilen SLO/alert kuralları (başlangıç):

| Kural | Koşul (rolling window) | Önerilen seviye | Operatör aksiyonu |
|---|---|---|---|
| Solver risk hard-stop | `skip_solver_risk_guard` >= 1 / 5 dk | `critical` | Promote dondur; QP/IK/ID residual ve limit violation trendini düşür |
| Stabilizasyon bekleme | `skip_solver_stabilization` >= 3 / 10 dk | `warn` | `stabilize_solver_convergence` runbook adımlarını uygula, sonra tekrar dene |
| Risk verisi kaybı | `skip_missing_risk_data` >= 3 / 10 dk | `warn` (20 dk sürerse `critical`) | Telemetri hattını (family_trends + solver_risk_score) geri getir |
| Readiness gate fail | `phase3.decision.decision=no-go` >= 3 ardışık poll | `warn` | `failed_gates` ve `policy_trace` üzerinden kök neden ayrıştır |
| Bridge kalite bozulması | `health_summary.diagnostics_reject_rate > 0.2` >= 2 / 5 dk | `critical` | Bridge/core hata sınıflarını incele, rollout'u güvenli profile çek |
| Rollout drift | `rollout_drift.has_drift=true` >= 10 dk | `warn` | Env/preset çakışmalarını temizle, tek policy kaynağına dön |

Prometheus/Grafana alert rule iskeleti (öneri):

- Örnek metric isimleri (topic payload'larından türetilmiş):
  - `control_core_autopilot_action_total{action,severity,reason_code}`
  - `control_core_phase3_decision_total{decision,severity,reason_code}`
  - `control_core_rollout_drift{profile}` (0/1 gauge)
  - `control_core_diagnostics_reject_rate` (gauge)
  - `control_core_solver_risk_score` (gauge)

```yaml
groups:
  - name: control-core-phase3
    rules:
      - alert: ControlCoreSolverRiskHardStop
        expr: increase(control_core_autopilot_action_total{action="skip_solver_risk_guard"}[5m]) >= 1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Solver risk guard triggered"
          description: "Autopilot promotion blocked by solver risk threshold."

      - alert: ControlCoreRiskDataMissing
        expr: increase(control_core_autopilot_action_total{action="skip_missing_risk_data"}[10m]) >= 3
        for: 2m
        labels:
          severity: warn
        annotations:
          summary: "Risk telemetry missing"
          description: "family_trends and/or solver_risk_score pipeline degraded."

      - alert: ControlCoreReadinessNoGoStreak
        expr: increase(control_core_phase3_decision_total{decision="no-go"}[10m]) >= 3
        for: 1m
        labels:
          severity: warn
        annotations:
          summary: "Repeated no-go decisions"
          description: "Inspect failed_gates and policy_trace for root cause."

      - alert: ControlCoreBridgeRejectRateHigh
        expr: max_over_time(control_core_diagnostics_reject_rate[5m]) > 0.2
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Bridge reject rate high"
          description: "Control-core bridge/core quality degraded."
```
- `control.core.rollout.result.health_summary` alan? operasyonel tek bak?? ?zetini verir (`decision`, `confidence`, `failed_gate_count`, `diagnostics_reject_rate`, `severity`).
- `health_summary.health_grade` (A/B/C/D) alan? dashboard taraf?nda h?zl? renk-kodlu durum takibi i?in sa?lan?r.
- `health_summary.failed_gates` ve `health_summary.health_grade` birlikte kullan?larak no-go kayna?? + genel kalite seviyesi tek alanda okunabilir.
- `health_summary.top_risk_families` ile en riskli command-family'ler reject_rate'e göre ilk 3 olarak sunulur.
- `health_summary.solver_risk_score`, `health_summary.solver_risk_level`, `health_summary.solver_risk_reasons` ile solver convergence kaynaklı operasyonel risk tek alanda okunur.

- Opsiyonel autopilot: `CONTROL_CORE_PHASE3_AUTOPILOT=1`
  - girdi: `control.core.phase3.decision`
  - ??kt?: `control.core.rollout.apply.request`, `control.core.phase3.autopilot.action`
  - sorgu: `control.core.phase3.autopilot.query` / `control.core.phase3.autopilot.result`
  - action code notları: `skip_solver_risk_guard`, `skip_missing_risk_data`, `skip_solver_stabilization`, `skip_noop`
  - güvenlik katmanı: `control.core.rollout.result.health_summary.top_risk_families` verisini kullanarak yüksek reject_rate family'ler i?in promote iste?ini `skip_risk_guard` ile engeller.

- Autopilot allowlist: `CONTROL_CORE_PHASE3_AUTOPILOT_ALLOWLIST=*|qp_solver,qp_controller,...`
- Autopilot tuning env: `CONTROL_CORE_PHASE3_AUTOPILOT_MIN_CONFIDENCE`, `CONTROL_CORE_PHASE3_AUTOPILOT_COOLDOWN_MS`
- Autopilot risk guard env: `CONTROL_CORE_PHASE3_AUTOPILOT_MAX_REJECT_RATE` (varsay?lan: `0.2`)
- Autopilot solver-risk guard env: `CONTROL_CORE_PHASE3_AUTOPILOT_MAX_SOLVER_RISK_SCORE` (profile preset varsayılanı: `s422_light=0.75`, `s422=0.6`, `default=1.0`)
- Opsiyonel strict risk-data guard: `CONTROL_CORE_PHASE3_AUTOPILOT_REQUIRE_RISK_DATA=1` ise ilgili family i?in reject-rate verisi yoksa autopilot `skip_missing_risk_data` yapar.
- Opsiyonel promotion-plan entegrasyonu: `CONTROL_CORE_PHASE3_AUTOPILOT_USE_PROMOTION_PLAN=1` iken decision aksiyonu spesifik de?ilse (`maintain_primary_stability` vb.) autopilot `control.core.phase3.promotion_plan.next_recommended_action` alan?n? fallback olarak kullan?r.
- Autopilot varsay?lanlar? profile preset'ten al?r (`CONTROL_CORE_CPP_PROFILE`), env varsa override eder.

Autopilot aksiyon state machine (özet):

| Girdi koşulu | Üretilen aksiyon |
|---|---|
| `recommended_next_action=stabilize_solver_convergence` | `skip_solver_stabilization` |
| `solver_risk_score > max_solver_risk_score` | `skip_solver_risk_guard` |
| `CONTROL_CORE_PHASE3_AUTOPILOT_REQUIRE_RISK_DATA=1` ve risk verisi eksik | `skip_missing_risk_data` |
| `recommended_next_action=maintain_primary_stability` (veya promote adımı yok) | `skip_noop` |
| Confidence/allowlist/cooldown geçerli + promote adımı belirlenmiş | `apply` ( `control.core.rollout.apply.request` yayınlanır ) |

Autopilot action -> alert mapping (öneri):

| Action (`last_action.action`) | Önerilen alarm seviyesi | Operasyon notu |
|---|---|---|
| `apply` | `info` | Beklenen rollout ilerlemesi. |
| `skip_noop` | `info` | O tur için promotable adım yok, izlemeye devam. |
| `skip_missing_risk_data` | `warn` | Risk telemetrisi eksik; veri hattı kontrol edilmeli. |
| `skip_solver_stabilization` | `warn` | Solver stabilizasyonu tamamlanmadan promote yapılmaz. |
| `skip_solver_risk_guard` | `critical` | Yüksek solver riski nedeniyle promote kilitlendi; önce solver tuning gerekir. |

Önerilen alarm payload sözleşmesi (dashboard/alert):

```json
{
  "action": "skip_solver_risk_guard",
  "severity": "critical",
  "reason_code": "solver_risk_threshold_exceeded",
  "runbook_hint": "Tune QP/IK/ID convergence; retry promotion after risk drops.",
  "source_topic": "control.core.phase3.autopilot.result",
  "ts_ms": 1760000000123
}
```

Reason code öneri listesi:

- `apply` -> `rollout_apply_sent`
- `skip_noop` -> `no_promotable_action`
- `skip_missing_risk_data` -> `risk_data_missing`
- `skip_solver_stabilization` -> `solver_stabilization_required`
- `skip_solver_risk_guard` -> `solver_risk_threshold_exceeded`

Solver risk operasyon runbook:

- `solver_risk_level=low`: rollout devam eder; planlı promote sırası korunur.
- `solver_risk_level=medium`: promote hızı düşürülür; `solver_risk_reasons` ve family trendleri izlenir.
- `solver_risk_level=high`: autopilot promote adımı beklenen olarak durur (`skip_solver_risk_guard`); `recommended_next_action=stabilize_solver_convergence` ise autopilot bu durumu `skip_solver_stabilization` olarak açıkça işaretler.

- Phase3 gate env: `CONTROL_CORE_PHASE3_MIN_CANDIDATE_COVERAGE`, `CONTROL_CORE_PHASE3_MIN_PRIMARY_COVERAGE`, `CONTROL_CORE_PHASE3_MAX_ERROR_RATE`.
- Phase3 solver-risk gate env: `CONTROL_CORE_PHASE3_MAX_SOLVER_RISK` (profile preset varsayılanı: `s422_light=0.8`, `s422=0.65`, `default=1.0`).

- Readiness threshold kayna??: `threshold_policy.profile`, `threshold_policy.preset`, `threshold_policy.sources` (env/profile_preset).
- Readiness gate görünürlüğü: `gates.solver_risk_gate` ve `gates.max_solver_risk_for_go` alanları solver-risk kaynaklı go/no-go kararını açıkça gösterir.
- Readiness bridge telemetry: `bridge.core_diagnostics.family_stats` ve `bridge.core_diagnostics.unknown_count` ile command-family bazlı accepted/rejected görünürlüğü sağlar.
- Readiness trend metriği: `bridge.core_diagnostics.family_trends` alanı family bazında `accepted_rate` / `rejected_rate` yayınlar.
- Promotion planner: `control.core.phase3.promotion_plan` topic'i family trendlerine göre promotable/blocked modülleri ve `next_recommended_action` üretir.

- Decision i?inde `policy_trace` bulunur; gate baz? pass/fail ve beklenen-ger?ek de?erleri raporlar.
- Decision i?inde `failed_gates` dizisi de vard?r; sadece fail olan gate adlar?n? listeler.
- Decision aksiyon önceliği: solver-risk gate fail olduğunda önerilen aksiyon `stabilize_solver_convergence` olur.
