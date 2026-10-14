# Controller / Estimator Depth v1

Bu belge humanoid kontrol katmanında `balance-aware` davranıştan daha ileriye giden ilk production-aday ayrımı özetler.

## Amaç

Kontrol kararı artık yalnızca action parametreleri ve kaba denge sinyalleriyle verilmez. Gait fazı, ayak temas tutarlılığı, estimator backend tazeliği ve QP solver modu aynı evidence zincirinde taşınır.

## Eklenen yüzeyler

| Yüzey | Sorumluluk |
|-------|------------|
| `core.controllers.gait_phase_manager` | Planlanan adım zamanlaması + gözlenen temaslardan `gait_phase.manager.v1` status üretir |
| `locomotion.gait_phase_status` | Beklenen destek/swing ayağı, geç touchdown, destek kaybı, faz kalitesi ve recovery gate yayınlar |
| `estimation.backend_status` | Native/real estimator backend tazeliği, confidence ve capability bilgisini görünür yapar |
| `estimation.robot_state.backend_evidence` | Backend base/contact/balance kanıtını unified state içinde taşır |
| `whole_body.qp_command.control_evidence` | QP komutunun hangi gait/backend kanıtıyla üretildiğini kaydeder |
| `locomotion.safety_state` | Estimator, gait phase, contact/slip, QP, native status ve fall recovery kanıtlarını tek safety kararı altında toplar |

## Kontrol davranışı

`WholeBodyQPControllerModule` şu durumlarda solver modunu sertleştirir:

| Kanıt | Sonuç |
|-------|-------|
| `support_mismatch=true` veya `recovery_gate=support_lost` | `capture_qp` |
| `late_touchdown=true` veya `recovery_gate=hold_for_contact` | `capture_qp` |
| `phase_quality < 0.68` | `nominal_qp` yerine `guarded_qp` |

Gait fazı aynı zamanda contact target dağılımını etkiler: single-support sırasında beklenen support foot daha yüksek normal kuvvet oranı alır, touchdown sırasında swing foot kademeli olarak tekrar yüke girer.

## Estimator guard contract

Core controller helper'ları artık estimator/contact güvenilirliğini yalnızca
serbest metin reason olarak değil, makine-okunur guard kararı olarak taşır:

- `estimator_guard.risk`
- `estimator_guard.hold_required`
- `estimator_guard.guard_action`
- `estimator_guard.allowed_solver_modes`
- `estimator_guard.guard_score`
- `estimator_guard.reasons`

Bu alanlar safety/router katmanlarının string reason parse etmeden
`guarded_qp`, `capture_qp` veya `safe_hold_wbc` kararını doğrulamasını sağlar.

## Estimator backend ilkesi

`StateEstimatorModule` Python tabanlı core estimate üretmeye devam eder. Native/real backend şu an güvenli şekilde evidence olarak taşınır:

- `estimation.backend_state` ve `estimation.real_backend_state` kabul edilir.
- 250 ms altı backend taze kabul edilir.
- `prefer_backend=true` verilirse ve confidence yeterliyse base alanı backend ile fuse edilir.
- Backend contact/balance kanıtı `core_primitives.backend_*` altında saklanır.

## Locomotion safety supervisor

`LocomotionSupervisorModule` artık yalnızca fall/slip/degraded mode izleyicisi değildir. Aşağıdaki girdileri tek karar kontratında birleştirir:

- `estimation.backend_status`
- `locomotion.gait_phase_status`
- `locomotion.contact_stability`
- `whole_body.qp_command`
- `whole_body.real_qp_solution`
- `native_control.status`
- `recovery.fall_status`

Yayınlanan canonical karar:

- topic: `locomotion.safety_state`
- schema: `locomotion.safety_supervisor.v1`
- mode: `nominal`, `guarded_replan`, `fall_recovery`, `safe_freeze`, `controlled_sit`
- supervisor_action: `continue`, `slow_down`, `capture_or_hold`, `freeze_or_hold_for_contact`, `getup_sequence`, `safe_stop`, `controlled_sit`

Fail-closed öncelik sırası:

1. safety-stop, fall detected, actuator trip, protective degraded mode
2. native control fault/deadline miss
3. QP solver failure
4. estimator backend critical/stale+low confidence
5. gait support loss
6. active fall recovery/get-up sequence
7. guarded replanning for estimator, gait, slip, capture or QP guard

## Sim/replay evidence

`core.tools.run_locomotion_stability_sim_suite` artık 8 vaka üretir:

- `stand_balance`
- `short_walk`
- `turn_and_stop`
- `disturbance_recovery`
- `estimator_dropout_guard`
- `getup_sequence_supervision`
- `support_loss_safe_stop`
- `safety_transition_soak`

Rapor özeti `locomotion_safety_state_count` ve `locomotion_safety_score` alanlarını da taşır. Böylece release evidence yalnızca hareket çıktılarına değil, güvenlik kararlarının gözlenen davranışına da dayanır.

Tek koşuyu soak kanıtına çevirmek için:

```bash
python -m core.tools.run_locomotion_safety_soak \
  --report-out logs/locomotion/locomotion_safety_soak.json \
  --cycles 3
```

Bu araç her cycle için ayrı `locomotion_stability_cycle_*.json` artifact üretir, SHA256 özetini
ana rapora yazar ve safety transition histogramını (`nominal`, `guarded_replan`,
`fall_recovery`, `safe_freeze`) toplar.

Kayıtlı HIL/robot telemetry stream'i shadow evidence olarak doğrulamak için:

```bash
python -m core.tools.locomotion_hil_trace_capture \
  --profile embodied_real_hardware \
  --trace-out logs/locomotion/hil_shadow_trace.jsonl \
  --report-out logs/locomotion/hil_trace_capture_report.json \
  --deployment-evidence hil_shadow_trace \
  --replay-report-out logs/locomotion/locomotion_telemetry_replay_evidence.json
```

Bu capture aracı varsayılan olarak yalnızca replay input topic'lerini JSONL trace'e yazar;
`locomotion.safety_state` ve hardware command topic'lerini ise rapor için gözler. Shadow
capture sırasında hardware command gözlenirse capture raporu fail-closed olur.

```bash
python -m core.tools.locomotion_telemetry_replay_evidence \
  --trace logs/locomotion/hil_shadow_trace.jsonl \
  --report-out logs/locomotion/locomotion_telemetry_replay_evidence.json \
  --deployment-evidence hil_shadow_replay
```

Replay raporu `estimation.backend_status`, `locomotion.gait_phase_status`,
`whole_body.qp_*`, `native_control.status`, `hardware.servo_plan_status` ve
`control.loop.replanning` konularını zorunlu kanıt kabul eder. Varsayılan gate
`nominal`, `guarded_replan` ve `safe_freeze` safety mode'larını bekler ve shadow
replay sırasında hardware command topic'i yayımlanırsa fail-closed sonuç üretir.

Native HIL, trace capture, telemetry replay ve safety soak raporlarını tek kabul
paketine çevirmek için:

```bash
python -m core.tools.locomotion_hil_acceptance_pack \
  --native-hil-report logs/hil_acceptance/native_command_frame_acceptance.json \
  --trace-capture-report logs/locomotion/hil_trace_capture_report.json \
  --telemetry-replay-report logs/locomotion/locomotion_telemetry_replay_evidence.json \
  --safety-soak-report logs/locomotion/locomotion_safety_soak.json \
  --out logs/locomotion/locomotion_hil_acceptance_pack.json
```

Bu pack PASS olduğunda release matrix `controller_estimator_depth` maddesini
`hil_acceptance_verified` olarak işaretleyebilir. Bu hâlâ robot saha/soak iddiası
değildir; HIL shadow acceptance kanıtıdır.

Tüm zinciri tek komutla üretmek için:

```bash
python -m core.tools.locomotion_hil_evidence_pipeline \
  --out-dir logs/locomotion/hil_evidence_pipeline \
  --trace-capture-report logs/locomotion/hil_trace_capture_report.json \
  --telemetry-trace logs/locomotion/hil_shadow_trace.jsonl \
  --safety-soak-cycles 3
```

Bu pipeline native command-frame HIL kabulünü, safety soak koşusunu, telemetry
replay kanıtını, acceptance pack üretimini ve `acceptance_pack_verification`
doğrulamasını aynı raporda toplar. Pipeline PASS olduğunda release matrix
`controller_estimator_depth` maddesini `hil_pipeline_verified` olarak
işaretleyebilir.

Gerçek HIL/robot raporlarında `provenance` bloğu zorunlu kabul edilir. Shadow/offline
raporlar bu alan eksikse geriye uyumlu kalır; fakat `deployment_evidence` içinde
`real`, `robot`, `physical`, `field` veya `production` geçen raporlar şu metadata
alanları eksikse fail-closed sonuç üretir:

- `commit_sha`
- `robot_device_id`
- `mcu_firmware_version`
- `actuator_firmware_version`
- `calibration_hash`
- `operator_id`
- `test_stand_id`
- UTC zaman, monotonic clock ve host/kernel/RT configuration bilgisi

Bu alanlar CLI argümanlarıyla veya ortam değişkenleriyle verilebilir:

```bash
HUMANOID_ROBOT_DEVICE_ID=robot-alpha-01 \
HUMANOID_MCU_FIRMWARE_VERSION=mcu-2.4.1 \
HUMANOID_ACTUATOR_FIRMWARE_VERSION=actuator-5.8.0 \
HUMANOID_CALIBRATION_HASH=calib-0123456789abcdef \
HUMANOID_OPERATOR_ID=operator-mehmet \
HUMANOID_TEST_STAND_ID=hil-stand-a \
HUMANOID_RT_CONFIG=preempt-rt \
python -m core.tools.locomotion_hil_evidence_pipeline \
  --telemetry-deployment-evidence production_robot_hil \
  --out-dir logs/locomotion/production_robot_hil_evidence \
  --telemetry-trace logs/locomotion/real_hil_trace.jsonl \
  --trace-capture-report logs/locomotion/real_hil_trace_capture_report.json
```

## Kalan olgunlaşma işleri

Bu seviye gerçek humanoid kontrol için önemli bir eşiktir, fakat tam L4/L5 için şu işler ayrıca gerekir:

- Donanım zaman damgası ve clock sync ile backend freshness doğrulaması.
- Contact estimator için force/torque, IMU ve vision temas kanıtının probabilistic fusion modeli.
- Gerçek robotta QP solver constraint violation telemetry ve HIL threshold kalibrasyonu.
- Fall recovery controller'ın gait phase manager recovery gate'lerini daha ince stage seçimine bağlaması.
- Slip, missed touchdown ve support-loss senaryolarının uzun koşu/soak testleri.
