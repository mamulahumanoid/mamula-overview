# Layer Boundaries

Bu doküman `core`, `adapters`, `native`, `ops` sınırlarını netleştirir.

İlgili özet: `architecture_index.md`.

## Hedef katmanlar

- **Core (`core/`)**
  - platform bağımsız iş mantığı
  - task/planning/world-model/policy/contracts/eventing/memory abstractions
- **Adapters (`core/adapters/`)**
  - dış sistem giriş noktaları (sim, hardware, audio, vision backend, native bridge)
- **Platform packages**
  - ağır/opsiyonel alanlar (`native/`, sim runtime, trainer fleet, deneysel paketler)
- **Ops (`ops/`)**
  - deploy/release/build automation

## Kritik kurallar

Core foundation paketlerinde (`core/bus`, `core/brain`, `core/contract`, `core/memory`, `core/runtime`):

- Isaac/Omniverse özel import **olmamalı** (`omni.*`, `pxr`, `isaacsim`)
- Native build çıktısı path varsayımı **olmamalı**
- Model artifact path varsayımları platform katmanına bırakılmalı

## Uygulanan guardrails

- Native bridge varsayılan binary yolu adapter katmanına taşındı:
  - `core/adapters/native_control_paths.py`
- Sınır testleri:
  - `core/tests/test_layer_boundaries.py`
    - foundation katmanda platform-import sızıntısı kontrolü
    - `native/control_core/build` literalinin adapter/tool/script/test dışına sızmaması

## Not

Bu sınırlandırma kademeli uygulanır. Mevcut modüller taşınırken:

1. önce adapter wrapper eklenir
2. core içinden wrapper çağrılır
3. sonra platform-spesifik modül gövdesi adapter/platform paketine aktarılır
