# Donanım hard safety mimarisi (MAMULA ile ilişki)

Bu belge, gerçek robotta **acil durdurma ve güvenli durma** için yetki sırasını tanımlar. Amaç: Python süreci, LLM veya üst seviye mantık çökse bile sistemin güvenli kalması.

## Yetki kuralı

- **MAMULA (bu repo, Python, üst seviye kararlar)** güvenlik için *danışman* ve *politika* katmanıdır: komutları reddedebilir, `SAFE_STOP` isteği gönderebilir, telemetry bayatlığını ve estop bayraklarını okuyabilir.
- **Son güvenlik yetkisi** her zaman **düşük seviye hard safety** katmanındadır: MCU / motion controller / güç elektroniği / bağımsız güvenlik zinciri.

Yazılımın `SAFE_STOP` veya komut kesmesi, **best-effort bir istek**tir; fiziksel estop, güç kesme ve kontrolcü içi acil durma **buna bağlı olmadan** çalışmalıdır.

## Hard safety (donanım / firmware, MAMULA’dan bağımsız)

Aşağıdakiler **Python sürecinden bağımsız** tasarlanmalı ve doğrulanmalıdır:

| Bileşen | Beklenti |
|--------|-----------|
| Fiziksel estop | Operatör müdahalesi; yazılım çökse bile aktif kalır. |
| Bağımsız motor güç kesme | Estop veya güvenlik rölesi ile kontaktör / STO / IL tarafı. |
| Watchdog | MCU / motion stack üzerinde; üst bilgisayar donarsa veya ağ koparsa zaman aşımına düşüp güvenli duruma geçer. |
| Düşük seviye emergency stop | Servo sürücü veya joint controller içinde fault → torque off / brake. |
| Ağ kopması → safe stop | Link kesildiğinde kontrolcünün kendi zaman aşımı ve güvenli durma politikası (Python’a güvenilmez). |
| Telemetry / iletişim bayatlığı → safe stop | Üst katmandaki `telemetry_stale` gate’i **ek** bir koruma katmanıdır; asıl karar kontrolcü tarafında olmalıdır. |

## Yazılım tarafında (MAMULA) ne yapılıyor?

Bu repo içinde örnekler:

- Gate ve latch: `estop_active`, telemetry stale, watchdog özeti (`bridge_contract`, `RealRobotAdapter`, executive bridge).
- Komut akışında başarısızlıkta `safe_stop` çağrısı (`hardware_command_execution.execute_hardware_command`).
- Telemetry’de `estop_active` ve fault alanlarının işlenmesi.

Bunlar **üst seviye uyumluluk ve raporlama** içindir; hard safety’nin yerini almaz.

## Tasarım kontrol listesi (saha)

1. Estop zinciri ve güç kesme şeması dokümante; yazılımın tek başına motor gücünü “açık tutma” yetkisi yok.
2. Motion controller / MCU watchdog süresi ve güvenli durma davranışı üst bilgisayardan bağımsız test edildi.
3. Ağ/protokol kopması senaryosu (EtherCAT/serial/UDP) kontrolcü tarafında zaman aşımı ile kapatıldı.
4. Üst katmandaki `SAFE_STOP` kaydı ve log, olay sonrası analiz içindir; tek güvenlik mekanizması olarak kullanılmaz.

İlgili belgeler: `real_robot_bridge_contract_v1.md`, `control_plane_python_vs_native.md` (kontrol düzlemi), `architecture_index.md`.
