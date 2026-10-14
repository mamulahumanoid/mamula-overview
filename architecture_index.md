# Mimari indeks

Robot ve çalışma zamanı için birbirini tamamlayan belgelerin kısa haritası.

Depo kökündeki [`README.md`](../../README.md) kurulum, ilk çalıştırma ve üst seviye mimari için **giriş noktasıdır**; gerçek robotta güvenli rollout özeti (shadow → HIL → bench → gözetimli …), `MAMULA_HARDWARE_SHADOW_COMMANDS` ve C++ shadow bayraklarına kısa bağlantılar orada özetlenir. Teknik ayrıntı ve tablo haritası için bu dosyaya dönün.

## Güvenlik ve donanım köprüsü

| Belge | Konu |
|-------|------|
| `gateway_runtime_hardening_stage1.md` | HTTP gateway: auth, şema, rate limit, audit, güvenli config (Aşama 1) |
| `hardware_hard_safety_architecture.md` | Hard safety vs MAMULA (Python) yetkisi; estop, watchdog, güç kesme |
| `real_robot_shadow_transition_v1.md` | Shadow → HIL → bench → low-speed supervised → limited autonomous task → tam; `MAMULA_HARDWARE_SHADOW_COMMANDS`, komut günlükleri |
| `real_robot_minimum_readiness_checklist_v1.md` | Minimum checklist + kanıt eşlemesi; **`scripts/verify_robot_readiness.sh`**, **`scripts/verify_physical_readiness.sh`**, `mamula doctor --physical-gates`, `mamula bringup-report` |
| `real_robot_bridge_contract_v1.md` | Adapter çıktı sözleşmesi, gate kodları, köprü alanları |

## Kontrol düzlemi (Python vs native)

| Belge | Konu |
|-------|------|
| `control_plane_python_vs_native.md` | Üst seviye Python vs gerçek zamanlı C++/MCU sınırı; native/control_core rolü |
| `controller_estimator_depth_v1.md` | Gait phase manager, real estimator backend evidence ve QP control evidence zinciri |
| `support_region_v2.md` | World-frame sole/contact patch convex hull, polygon halfspaces ve contact wrench cone sözleşmesi |
| `cpp_low_level_migration_v1.md` | C++ çekirdeğe geçiş fazları, bridge env’leri, rollout bayrakları |
| `real_time_control_core_stage5.md` | **Aşama 5:** gerçek zamanlı çekirdek bileşenleri (scheduler, IK, QP/ID, limitler, düşme, watchdog); Python→native→HAL akışı |

## Donanım soyutlama (HAL)

| Belge / modül | Konu |
|---------------|------|
| `hardware_abstraction_layer_v1.md` | Aşama 4: Motor/Servo/IMU/kamera/BMS/estop… sürücü telemetrisi ve lifecycle |
| `core/hardware/hal_driver_contract_v1.py` | `DriverTelemetryV1`, `DriverLifecycleState` |
| `core/hardware/hal_driver_base.py` | Sürücü sınıfları, `default_hal_registry` |

## Yaşam döngüsü (OS — güvenli açılış)

| Belge / modül | Konu |
|---------------|------|
| `lifecycle_manager_stage6.md` | **Aşama 6:** config→hardware→sürücü→kalibrasyon→sensör→güvenlik→kontrol çekirdeği→AI→skill sırası; IMU/kamera/telemetri yetenek kapıları |
| `runtime_supervisor_v1.md` | **OS yol haritası:** Supervisor + Module Manager + Bus Router; lifecycle hook’ları, load-order doğrulama, supervised tick, çok proses hedefi |
| `core/contract/lifecycle_readiness_v1.py` | `ORDERED_PHASES`, `capability_snapshot`, `infer_camera_present`, `LIFECYCLE_STATUS_TOPIC` |
| `core/modules/robot/lifecycle_readiness_module.py` | `lifecycle.status` yayıncısı |

## AI / Hafıza / Öğrenme

| Belge / araç | Konu |
|--------------|------|
| `ai_memory_deep_learning_acceptance_v1.md` | AI-hafıza-deep-learning kabul kapısı; memory lineage, model card, canary, runtime health, privacy redaction |
| `core/tools/ai_memory_dl_acceptance.py` | `python -m core.tools.ai_memory_dl_acceptance --strict` acceptance raporu |
| `core/learning/deep_learning_governance.py` | Model card, memory preflight, promotion, runtime health ve remediation planları |
| `core/learning/memory_shadow_canary_pipeline.py` | Memory bundle → trainer → canary/promotion raporu |
| `local_rag_v1.md` | Ağsız doküman ingest, FTS5/Qwen3 hibrit retrieval, ACL, citation ve abstention kapıları |
| `core/tools/local_rag.py` | Özel yerel indeksi ingest/query/delete/stats komutlarıyla yönetir |
| `core/tools/local_rag_eval.py` | Donmuş, ağsız Local RAG qualification kapısını çalıştırır |
| `core/tools/local_rag_corpus_eval.py` | Gerçek yönetilen corpus için içerik/yol sızdırmayan hash'li qualification raporu üretir |
| `core/rag/intake.py` | `public`/`household`/`owner` kaynak köklerini ve yerel manifesti private izinlerle hazırlar |
| `core/rag/readiness.py` | İndeks, izin, qualification freshness ve runtime local-only binding kapılarını doğrular |
| `local_research_v1.md` | Ağsız çok-belgeli araştırma, kaynak çeşitliliği, citation, çelişki ve çekimserlik sözleşmesi |
| `core/research/service.py` | Local RAG üzerinden citation-bound evidence pack ve olası çelişki üretir |
| `core/tools/local_research_eval.py` | Donmuş Research v1 davranış kapısı |
| `core/tools/local_research_corpus_eval.py` | Gerçek corpus için içerik sızdırmayan aggregate qualification |

## Planlama / Behavior Tree

| Belge / modül | Konu |
|---------------|------|
| `behavior_tree_engine_v2.md` | Tick-based BT engine: `RUNNING`, blackboard, async action, cancellation, timeout |
| `core/modules/behavior_tree_engine_module.py` | `behavior.tree.run/tick/cancel/action.result` session motoru |
| `core/modules/planner_advanced_stack.py` | HTN/PDDL/LLM structured plan köprüsü |

## Algı / Vision 3D

| Belge / modül | Konu |
|---------------|------|
| `vision_3d_depth_fusion_v1.md` | RGB-D sync, 3D pose, depth fusion, object permanence, dataset fixture testi |
| `core/modules/robot/object_pose_estimation_module.py` | `object_pose.v1`, `depth_fusion.v1`, `sensor_sync.v1`, `object_permanence.v1` |
| `core/modules/robot/scene_understanding_module.py` | 3D pose/permanence alanlarını scene graph node’larına taşır |
| `core/modules/robot/perception_world_state_bridge_module.py` | Fused 3D alanları `perception.state` ve world-state akışına koruyarak geçirir |

## Mesaj sözleşmesi (EventBus zarfı)

| Belge / modül | Konu |
|---------------|------|
| `message_contract_v1.md` | Aşama 2: `schema_version`, `message_id`, `payload`, `ttl`, öncelik |
| `os_concepts_and_qos_v1.md` | topic/event/state/command/… kavramları + QoS profili (`reliable`, `latched_state`, …) |
| `distributed_transport_v1.md` | EventBus transport olgunluğu: `inproc` stable, `file_replay` beta, `unix_socket` experimental |
| `core/contract/message_envelope_v1.py` | Zarf üretimi, doğrulama, canonical topic aliasları |
| `core/contract/os_concepts_v1.py` | `OsConcept` enum — resmi kavram etiketleri |
| `core/contract/qos_profile_v1.py` | `QosProfileV1`, zarf altında `qos` |

## Gözlemlenebilirlik, günlük, replay

| Belge / araç | Konu |
|--------------|------|
| `diagnostics_log_replay_stage7.md` | **Aşama 7:** event timeline, task/safety/LLM trace, kontrol gecikmesi, sensör/HAL, episode recorder, failure snapshot, replay |
| `core/contract/diagnostics_observability_v1.py` | `TraceKind`, timeline şema sürümü |
| `core/modules/event_recorder_module.py` | Tam oturum JSONL (`session_*.jsonl`) |
| `core/modules/motion_trace_module.py` | Hareket özeti JSONL |
| `core/modules/reasoning_trace_aggregator_module.py` | Reasoning izi + opsiyonel SQLite |
| `core/tools/mamula_cli.py` | CLI: `mamula doctor`, `diagnostics`, `logs`, `trace task`, `replay last-failure` |
| `core/utils/failure_snapshot.py` | `mamula.failure_snapshot.v1` JSON anlık görüntüleri |
| `core/modules/robot/failure_snapshot_module.py` | Güvenlik latch olayında snapshot |

## CLI ve dağıtım

| Belge / yol | Konu |
|-------------|------|
| `cli_deployment_stage8.md` | **Aşama 8:** `mamula run profile`, skills/drivers listeleri, günlük, config validate, update/rollback; sırlar, sürüm |
| `deploy/systemd/mamula-runtime.service` | Örnek systemd birimi |
| `deploy/docker/Dockerfile` | Minimal çalışma zamanı imajı |
| `deploy/jetson/README.md` | Jetson notları |

## Skill SDK / plugin

| Belge / modül | Konu |
|---------------|------|
| `skill_sdk_plugin_stage9.md` | **Aşama 9:** `register_skill`, ön/son koşullar, risk, yetenekler, timeout, recovery, sim/hardware, test_suite |
| `skill_maturity_v1.md` | Public skill olgunluk ayrımı: `mvp_hardened`, `experimental`, `catalog_only` |
| `core/skills/sdk.py` | `register_skill`, `get_skill_handler` — katalog + handler tablosu |
| `core/modules/robot/robot_skill_catalog.py` | Birleşik skill listesi (`register_extension_skills`) |

## Sim / HIL / gerçek robot (tek sözleşme)

| Belge / modül | Konu |
|---------------|------|
| `sim_hil_real_contract_stage10.md` | **Aşama 10:** aynı canonical topic yüzeyi (`skill.*`, `control.*`, `safety.event`); fark yalnız adapter |
| `core/contract/unified_runtime_surface_v10.py` | `EXECUTION_SURFACE_TOPICS`, `wire_topic()` |

## Denge ve yürüyüş kontrolü

| Belge / modül | Konu |
|---------------|------|
| `support_region_v2.md` | Dünya-frame ayak/contact polygonları, convex hull ve eğimli/çoklu temas wrench cone sözleşmesi |
| `kinodynamic_gait_v2.md` | Reduced-order LIPM/DCM foot placement, reachable region, minimum-jerk 6DoF swing/pelvis, online retiming ve kanıt sınırı |
| `core/controllers/kinodynamic_gait_planner.py` | Saf trajectory, quaternion, reachability ve late-touchdown retiming primitive'leri |
| `core/modules/robot/gait_trajectory_generator_module.py` | `world_footstep_plan.v1`, `gait.trajectory.v2` ve per-tick `gait.setpoint.v1` yayıncısı |

## Test ve CI

| Belge | Konu |
|-------|------|
| `test_tiers_ci.md` | Marker’lar, skip politikası; `mamula test` tier / `hil` / `native` ile pytest eşlemesi; workflow `test-tiers.yml` özeti |
| `cli_deployment_stage8.md` | `mamula` CLI (`bringup-report`, `doctor --physical-gates`, …) |

## Repo yapısı ve konular

| Belge | Konu |
|-------|------|
| `layer_boundaries.md` | `core` / `adapters` / `native` / `ops` sınırları |
| `topic_atlas.md` | Event-bus topic haritası |

Üst kök (onboarding ve özet): [`README.md`](../../README.md) — native build, `CONTROL_CORE_*`, adapter/shadow notları.
