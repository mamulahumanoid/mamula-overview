# Compute Trainer Backend v1

## Amaç
Canlı öğrenme çekirdeğinin üstüne ayrı bir compute-trainer katmanı ekler.
Bu katman sim benchmark campaign sonuçlarını, online learning state verisini ve mevcut biometric/policy profillerini kullanarak:
- fine-tune benzeri policy export
- RL refinement export
- biometric distillation export
- distilled policy bundle
üretir.

## Ana Olaylar
- `learning.compute_trainer.submit`
- `learning.compute_trainer.query`
- `learning.compute_trainer.apply_export`
- `learning.compute_trainer.reset_registry`
- `learning.compute_trainer.job_submitted`
- `learning.compute_trainer.export_ready`
- `learning.compute_trainer.apply_result`
- `learning.compute_trainer.result`
- `learning.compute_trainer.status`

## Kalıcı Dosyalar
- `data/learning/model_registry.json`
- `data/learning/jobs/*.json`
- `data/learning/exports/*_export.json`

## Kullanım
### Runtime üzerinden job üretme
`learning.compute_trainer.submit`
- `trainer_type`: `full_stack`, `policy_finetune`, `rl_refinement`, `biometric_distillation`
- `requested_mode`: `shadow`, `canary`, `apply`
- `campaign_result`: opsiyonel campaign payload
- `online_state`: opsiyonel live adaptive learning state

### Export uygulama
`learning.compute_trainer.apply_export`
- `export_path`: üretilecek export dosyası

Bu olay sonrasında sistem otomatik olarak şunları yayınlar:
- `learning.online_policy_update`
- `learning.online_biometric_threshold_update`

## CLI
```bash
python3 -m core.tools.run_compute_trainer_backend \
  --campaign-report ./data/reports/campaign.json \
  --online-state ./data/learning/live_adaptive_learning_state.json \
  --trainer-type full_stack \
  --requested-mode canary \
  --out-export ./data/learning/exports/manual_compute_trainer_export.json
```

## Not
Bu sürüm gerçek GPU tabanlı gradient trainer'ın runtime omurgasını ve export/registry kontrol düzlemini sağlar.
Yani üretim tarafında:
- job staging
- export generation
- deploy/apply
- model registry
- shadow/canary/apply
hazırdır.
Gerçek büyük model optimizer, distributed trainer ve RL learner worker'ları bu katmanın arkasına bağlanacak şekilde tasarlanmıştır.
