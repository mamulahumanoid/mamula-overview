# Approval By Exception Supervision v1

Bu paket, operator onay bağımlılığını tamamen kaldırmadan düşük riskli görevlerde otomatik akış sağlayan bir ara katman ekler.

## Amaç

- `operator_supervised_pick_and_bring` davranışını bozmadan approval-by-exception modeli eklemek.
- Düşük riskli navigation / pick / handover akışlarında inline auto-approval üretmek.
- Belirsiz veya riskli durumlarda açık exception kararı yayınlamak.
- Sim-ready dönemde insan onayını varsayılan değil istisna tabanlı hale getirmek.

## Eklenen modül

- `core/modules/robot/approval_by_exception_policy_module.py`

## Güncellenen modül

- `core/modules/robot/operator_supervised_pick_and_bring_module.py`

Bu modül artık sadece `operator.supervision.approval` ile gelen manuel onayları değil,
`params.operator_supervision.approved=true` veya `operator_approval_exempt=true`
şeklinde gelen inline policy approval'ları da kabul eder.

## Yeni runtime profili

- `s502`
- alias: `approval_by_exception_supervision`
- alias: `approval_by_exception`

Bu profil, `s501` üstüne şunları ekler:

- `integrated_task_bringup`
- `approval_by_exception_policy`
- `operator_supervised_pick_and_bring`

## Sağlanan olaylar

### Karar yayını

- `operator.supervision.decision`
- `operator.supervision.auto_approval`
- `operator.supervision.exception`

### Policy yönetimi

- `operator.supervision.policy.set`
- `operator.supervision.policy.query`
- `operator.supervision.policy.result`

## Varsayılan düşük risk kuralları

### GO_TO_LOCATION

Auto-approval için tipik koşullar:

- lokasyon boş değil
- policy içinde biliniyor
- insan çok yakın değil
- engel çok yakın değil

### PICK_OBJECT

Auto-approval için tipik koşullar:

- nesne perception içinde görünür
- confidence yeterli
- uncertainty düşük
- occluded değil
- grasp candidate skoru yeterli
- nesne current zone içinde
- insan çok yakın değil

### BRING_OBJECT_TO_USER

Auto-approval için tipik koşullar:

- target mevcut veya perception'da insan mevcut
- social policy safe + recipient locked
- force policy handover'a izin veriyor
- release verification hazır
- approach safe

## Tasarım ilkesi

Bu katman gerçek güvenlik yerine geçmez.
Amacı, simülasyon öncesi görev akışlarında gereksiz operator onayı yükünü azaltmak ve
onay gerektiren durumları makine-okunur biçimde görünür hale getirmektir.

## Test kapsamı

Yeni test dosyası:

- `core/tests/test_approval_by_exception_supervision.py`

Örnek senaryolar:

- düşük riskli `GO_TO_LOCATION` otomatik onay alır ve tamamlanır
- düşük confidence / occluded pick operator exception ister
- güvenli handover parametreleri ile `BRING_OBJECT_TO_USER` otomatik onay alır
