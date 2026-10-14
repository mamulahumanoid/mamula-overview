# Kontrol düzlemi: Python (üst seviye) vs native low-level çekirdek

Bu proje, **karar ve orkestrasyon** için Python kullanır; **deterministik, yüksek frekanslı kontrol** ise **C++/Rust veya MCU** tarafında kalmalıdır. `native/control_core/` bu sınır için iskelet çekirdektir; üretimde gerçek zamanlı servo/denge/QP katmanı buraya veya doğrudan motion-controller firmware’ine taşınır.

## Python tarafında kalması doğru olanlar

- Üst seviye davranış ve dil: LLM / ses / NL komut
- Görev planlama, skill seçimi, politika
- Hafıza, diyalog, bağlam
- Ops paneli, telemetri görselleştirme, loglama
- Güvenlik **politikası** ve kapılar (komutu reddetme, istek üzerine durdurma isteği — bkz. `hardware_hard_safety_architecture.md`)

Python burada **yumuşak gerçek zamanlı** çalışır; kontrol döngüsünün yerine geçmez.

## Python’da kalmaması gerekenler (native / RT dünyası)

| Alan | Gerekçe |
|------|---------|
| ~1 kHz servo komut döngüsü | Gecikme ve jitter toleransı Python’da uygun değil |
| Denge kontrolü, WBÇ temeli | Deterministik fizik + düşük latency |
| Eklem tork/akım kapalı döngü | Sürücü/MCU ile birlikte güvenlik zinciri |
| Düşme algısı ve recovery refleksi | Süre kritik; MCU veya native thread |
| Whole-body QP/MPC | Sayısal yoğun, kesin periyot |
| Motor / iletişim watchdog (hard) | Python çökse de tetiklenmeli |

Bu bileşenler **Rust/C++/RTOS** veya vendor motion stack içinde konumlanır; Python yalnızca üst seviye referans veya mod seçimi gönderebilir.

## Repo içi köprü

- **Native iskelet:** `native/control_core/` — CMake, `control_core_bridge` ikilisi, `mamula::control::ControlCore` API’si (latency/QP alanları telemetry için rezerve).
- **Python köprü modülü:** `core/modules/robot/cpp_control_bridge_module.py` — `CONTROL_CORE_BACKEND=cpp` ile süreç içi çağrı; üretimde gerçek düşük seviye süreç ile değiştirilir veya soket/SHM ile bağlanır.
- **Çevre değişkenleri (örnek):** `CONTROL_CORE_BRIDGE_BIN`, `CONTROL_CORE_BRIDGE_STRICT_CONTRACT` — `README.md` native bölümünde özetlenir.

## Hedef mimari

```
[ Python: AI / plan / gait + model-based WBC pipeline ]
        │ timestamped q / qdot / torque-ff / contact / impedance frame
        ▼
[ Native veya MCU: 500 Hz–1 kHz limiter + impedance/torque servo, watchdog, STO ]
        │
        ▼
[ Aktüatör / sürücü ]
```

Geçiş sözleşmesinde Python'daki model-tabanlı gait/WBC/QP/IK/ID zinciri
`mamula_wbc_command_frame_t` üretir; native çekirdek yalnız bu doğrulanmış,
deadline'lı frame'i uygular ve kendi başına gait uydurmaz. Nihai hard-RT
dağıtımında aynı frame sözleşmesi korunarak estimator ve sayısal WBC solver'ları
native RT process'e taşınabilir.

## İlgili dokümanlar

- `real_time_control_core_stage5.md` — Aşama 5 bileşen envanteri (scheduler, IK, QP/ID, limitler, düşme, watchdog) ve MAMULA→native→HAL akışı.
- `cpp_low_level_migration_v1.md` — faz planı, `CONTROL_CORE_BACKEND`, bridge rollout.
- `hardware_hard_safety_architecture.md` — Python’daki güvenlik kapıları ile MCU/donanım yetkisi ayrımı.
- `architecture_index.md` — bu dosyaların kısa indeksi.
