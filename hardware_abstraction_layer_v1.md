# Hardware Abstraction Layer (HAL) v1 — Aşama 4

`RobotHardwareInterface` eklem tabanlı durumu iyi bir başlangıçtır; tam OS için **sürücü bazlı** soyutlama gerekir. Bu katman, vendor SDK / MCU / fieldbus ayrıntılarını üst katmandan ayırır.

## Sürücü türleri (birinci dalga)

| Sınıf | `driver_kind` |
|-------|----------------|
| `MotorDriver` | `motor` |
| `ServoBusDriver` | `servo_bus` |
| `IMUDriver` | `imu` |
| `CameraDriver` | `camera` |
| `DepthCameraDriver` | `depth_camera` |
| `ForceTorqueDriver` | `force_torque` |
| `BatteryBMSDriver` | `battery_bms` |
| `GripperDriver` | `gripper` |
| `MicrocontrollerBridgeDriver` | `microcontroller_bridge` |
| `EmergencyStopDriver` | `emergency_stop` |

Kod: `core/hardware/hal_driver_base.py`. Varsayılan örnek kayıt: `default_hal_registry()`.

## Her sürücü telemetrisi (`DriverTelemetryV1`)

| Alan | Açıklama |
|------|-----------|
| `health` | `ok` / `degraded` / `critical` / `unknown` (`DriverHealth`) |
| `latency_ms` | Son ölçülen gidiş-dönüş veya işleme gecikmesi |
| `last_packet_ts_ms` | Son geçerli paket zaman damgası |
| `firmware_version` | Aygıt/bridge firmware veya sürücü sürümü |
| `temperature_c` | İsteğe bağlı (motor sürücü, BMS hücresi, …) |
| `voltage_v` / `current_a` | İsteğe bağlı güç yolu |
| `fault_code` | Sayı veya kısa kod; `None` = fault yok |
| `calibration_state` | Üretici-bağımsız etiket (örn. `uncalibrated`, `factory`, `field`) |
| `lifecycle_state` | Aşağıdaki durumlardan biri |

Wire format: `schema_version: mamula.hal.driver_telemetry.v1` (`to_dict()`).

## Yaşam döngüsü (`DriverLifecycleState`)

- `unconfigured` → `configured` → `calibrating` → `inactive` | `active`
- Hata: `fault`; kontrollü kapanış: `safe_shutdown`

`HalDriver.set_lifecycle(...)` ile güncellenir.

## Toplu görünüm

`aggregate_hal_snapshot(registry)` → `mamula.hal.aggregate.v1` — ops paneli / diagnostics için tüm sürücü satırları.

## Canlı telemetri senkronu

`HalRuntimeBridgeModule` (`hal_runtime_bridge`), `hardware.telemetry` yayınını dinler ve `sync_hal_from_telemetry(get_hal_registry(), frame)` ile varsayılan HAL kaydındaki `ingest_live` alanlarını günceller. Embodied gerçek donanım profillerinde (`specs_embodied_real_hardware`) bu modül `hardware_telemetry_bridge` sonrası yüklenir.

Ops JSON’da `hardware_telemetry_snapshot` çıktısı, birleşik HAL görünümünü **`hal`** anahtarıyla içerir (köprü yüklü değilken bile süreç içi kayıt anlık görünümü döner).

## İlişki

- **RobotHardwareInterface:** mevcut eklem/telemetry birleşik görünüm (embodiment, sim).
- **HAL:** aygıt sınıfı başına sözleşme; ileride `RobotHardwareInterface` HAL kayıtlarından beslenebilir.

İlgili: `hardware_hard_safety_architecture.md`, `control_plane_python_vs_native.md`.
