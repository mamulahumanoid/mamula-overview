# Embodied autonomy metrics v2

Bu turda household autonomy scorecard katmani genisletildi ve olay sayaci mantigindan cikartilarak embodied benchmark profiline tasindi.

## Eklenenler

- metrics version: `embodied_autonomy_metrics_v2`
- action latency takibi (`executive.action` -> `executive.action_result`)
- approval decision / auto approval / operator intervention sayaclari
- manipulation retry / escalation sayaclari
- perception reobserve ve correction sayaclari
- bridge gate block ve safety stop sayaclari
- first-pass ve recovered success ayrimi
- benchmark summary ve grade
- query sonucu icinde benchmark result yayini

## Profil

- `s503`
- alias: `autonomy_metrics_v2`
- alias: `embodied_autonomy_metrics`

## Stack

- `manipulation_autonomy_retry_recovery`
- `approval_by_exception_policy`
- `operator_supervised_pick_and_bring`
- `end_to_end_household_autonomy_scorecard`
- `hardware_bridge`

## Yeni alanlar

`RUN_HOUSEHOLD_AUTONOMY_SCORECARD` aksiyonu sonucunda su alanlar doner:

- `household_autonomy_scorecard_profile.metrics_version`
- `household_autonomy_scorecard_profile.embodied_autonomy_score`
- `household_autonomy_scorecard_profile.benchmark_summary`
- `household_autonomy_scorecard_profile.embodied_metrics`
- `household_autonomy_benchmark_summary`

## Query topicleri

- `domestic.household_autonomy_scorecard.query`
- `domestic.household_autonomy_benchmark.query`

Her iki query de su topiclere sonuc basar:

- `domestic.household_autonomy_scorecard.result`
- `domestic.household_autonomy_benchmark.result`

## Hedef

Bu katman sim oncesi hazirlik icin su sorulari cevaplar:

- Sistem ne kadar operator bagimli?
- Retry/recovery calisiyor mu?
- Algisal duzeltme davranisi var mi?
- Ilk denemede mi yoksa toparlayarak mi basari geliyor?
- Fiziksel aksiyonlarda latency ve gate block profili nasil?
