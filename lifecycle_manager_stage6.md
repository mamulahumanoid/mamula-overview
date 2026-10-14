# Yaşam döngüsü yöneticisi — Aşama 6 (OS güvenli açılış)

Tam bir işletim sistemi, modülleri **rastgele** değil **güvenli ve tekrarlanabilir bir sırayla** ayağa kaldırmalıdır. Ayrıca donanım/sensör koşullarına göre **yetenekleri** (walking, görsel seç-im gibi) açıp kapatmalı; telemetri güvenilmezken hareketi kilitlemelidir. Bu belge Aşama 6’nın **sözleşmesini** tanımlar; `RuntimeBootstrap` profil sırası bu sırayı desteklemeli, ileride merkezi bir `lifecycle` modülü `core/contract/lifecycle_readiness_v1.py` ile aynı faz ve yetenek isimlerini kullanmalıdır.

**İlgili:** `hardware_hard_safety_architecture.md`, `real_robot_bridge_contract_v1.md`, `real_time_control_core_stage5.md`, `hardware_abstraction_layer_v1.md`.

---

## Hedef açılış sırası (örnek)

Sıra atlamadan ilerlenmeli; bir faz başarısızsa sonrakiler **yetkilendirilmemiş** kabul edilir (fail-stop veya degraded mod politikası ayrı tanımlanır).

| # | Faz | Amaç |
|---|-----|------|
| 1 | **Config load** | Ortam, profil, eklem şeması, güvenlik eşikleri |
| 2 | **Hardware detect** | Bus üzerinden aygıt keşfi / HAL kaydı |
| 3 | **Driver configure** | Sürücüler `configured`/`active` yaşam döngüsü (HAL Aşama 4) |
| 4 | **Calibration check** | Kalibrasyon durumu kabul edilebilir mi |
| 5 | **Sensor health check** | IMU, kamera, kontakt, telemetri tazeliği (`robot.diagnostics`, `hardware.health`) |
| 6 | **Safety ready** | Estop zinciri, watchdog özeti, politika kapıları |
| 7 | **Control core arm** | Native kontrol çekirdeği devreye alma (`CONTROL_CORE_*`, bridge) |
| 8 | **AI runtime enable** | Üst seviye akıl / ses / executive güvenli mod |
| 9 | **Skills enable** | Skill kataloğu ve kullanıcıya açık davranışlar |

Bu liste **mantıksal** fazlardır; tek Python modülü = tek faz olmak zorunda değildir (ör. bir modül birden fazla fazın koşullarını doğrular).

---

## Yetenek kapıları (zorunlu kurallar)

| Koşul | Sonuç |
|--------|--------|
| **IMU yok** veya IMU sağlığı kötü | **Walking** (ve lokomosyon sınıfı hareket) **devre dışı** |
| **Kamera yok** veya görüntü akışı yok | **Visual pick** (görsel seç-im / görsel manipülasyon) **devre dışı** |
| **Telemetri bayat** (`telemetry_stale`, yaş > eşik) | **Tüm hareket** (motion) **devre dışı** — üst katman gate: `real_robot_adapter`, `action_router_module`, `voice_command_service` içindeki `telemetry_stale` davranışı ile uyumlu |

Öncelik: telemetri bayatlığı **tüm hareketi** keser; IMU/kamera eksiklikleri bundan sonra ikincil olarak ilgili alt yetenekleri kapatır (hareket zaten kapalıysa walking zaten yoktur).

Sözleşme sabitleri ve birleşik yetenek sözlüğü: `core/contract/lifecycle_readiness_v1.py` (`capability_snapshot`).

---

## Depo ile eşleme (mevcut işaretçiler)

| Kavram | Neresi |
|--------|--------|
| Profil / modül sırası | `RuntimeBootstrap`, `core/runtime/profile_specs/_generated.py` |
| Telemetri bayatlık kapısı | `core/modules/robot/real_robot_adapter.py`, `core/adapters/voice_command_service.py`, `core/modules/action_router_module.py` |
| Sensör sağlığı | `robot.diagnostics` / `RobotDiagnosticsV1Module`, `hardware.health` |
| HAL sürücü durumu | `core/hardware/hal_driver_contract_v1.py` (`DriverLifecycleState`) |
| Native kontrol silahlanma | Aşama 5: `cpp_control_bridge_module`, `native/control_core/` |

---

## Olay / topic yüzeyi

Taşıyıcı JSON için `schema_version: mamula.lifecycle.readiness.v1` kullanın.

- **`lifecycle.status`** — `LifecycleReadinessModule` tarafından yayınlanır: `capabilities`, `gates`, `phase`, `ts_ms`.
- **`lifecycle.command`** — operatör/test için faz ilerletme (ileride).

Yetenek hesaplaması tek yerde (`capability_snapshot`); modül bus üzerinden dağıtır. `ActionRouterModule` önce `lifecycle.status` ile özetlenmiş kapıları kullanır; yayın yoksa telemetri/diagnostics üzerinden aynı sözleşmeyi yerelde üretir.

---

## Uygulama (repo)

| Bileşen | Rol |
|---------|-----|
| `core/modules/robot/lifecycle_readiness_module.py` | `hardware.telemetry` + `robot.diagnostics.status` → `lifecycle.status` |
| `core/runtime/profile_specs/_generated.py` (`specs_default`) | `lifecycle_readiness` modülü `action_router` öncesine eklenir |
| `core/modules/action_router_module.py` | Davranış eylemleri ve `motion` rotası için motion/walking/visual_pick kapıları |
| `LIFECYCLE_CAMERA_STRICT` | `1` ise telemetride kamera ipucu yoksa `visual_pick` kapalı kabul edilir |

---

## Aşama 6 kabul ölçütleri (özet)

- [x] Açılış sırası dokümante; `specs_default` içinde lifecycle modülü sırası tanımlı.
- [x] IMU/kamera/telemetri kuralları `lifecycle_readiness_v1` ve action router ile uyumlu.
- [x] Telemetri bayatken hareket sınıfı eylemler reddedilir (`lifecycle_motion_disabled`).

Bu belge politika sözleşmesidir; faz makinesinin tam otomasyonu (`lifecycle.command`) ayrıca genişletilebilir.
