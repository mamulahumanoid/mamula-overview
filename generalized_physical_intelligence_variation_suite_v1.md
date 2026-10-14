# Generalized Physical Intelligence Variation Suite v1

Amaç: perception/manipulation/supervision zincirini sabit sahne testinden çıkarıp
seed'li, tekrar üretilebilir varyasyon benchmark'ına taşımak.

## Eklenen profil
- `s504`
- alias: `generalized_physical_intelligence_variation_suite`
- alias: `physical_intelligence_variation`

Bu profil, `s503` üstüne şunları ekler:
- `generalized_physical_intelligence_variation_suite`
- variation suite load/start/next/reset/query
- seed'li scenario generation
- difficulty score / band
- coverage ve robustness benchmark özeti

## Giriş olayları
- `physical_intelligence.variation_suite.load`
- `physical_intelligence.variation_suite.start`
- `physical_intelligence.variation_suite.next`
- `physical_intelligence.variation_suite.reset`
- `physical_intelligence.variation_suite.query`

## Çıkış olayları
- `physical_intelligence.variation_suite.result`
- `physical_intelligence.variation_suite.status`
- `physical_intelligence.variation_suite.scenario_started`
- `physical_intelligence.variation_suite.scenario_completed`
- `physical_intelligence.variation_suite.completed`
- `physical_intelligence.variation_suite.action_request`
- `physical_intelligence.variation_context`
- `physical_intelligence.variation_benchmark.result`

## Desteklenen varyasyon eksenleri
- occlusion / partial visibility
- obstacle / clutter injection
- label substitution
- grasp candidate drop
- pose jitter (m / deg)
- confidence drift
- uncertainty drift

## Benchmark özeti
Üretilen benchmark summary içinde:
- `total_scenarios`
- `completed_scenarios`
- `successful_scenarios`
- `verified_successful_scenarios`
- `average_difficulty_score`
- `difficulty_coverage`
- `success_rate_pct`
- `verified_success_rate_pct`
- `independence_score`
- `recovery_score`
- `perception_score`
- `robustness_score`
- `success_rate_by_difficulty_pct`
- `benchmark_grade`

## Scorecard entegrasyonu
`end_to_end_household_autonomy_scorecard` artık son variation benchmark özetini de
saklar ve `RUN_HOUSEHOLD_AUTONOMY_SCORECARD` çıktısına:
- `physical_intelligence_variation_summary`
alanı olarak ekler.
