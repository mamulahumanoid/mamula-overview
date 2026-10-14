# live adaptive learning engine v1

Bu katman robotun çalışırken politika ve eşik öğrenmesini yapar.

## Sağladıkları
- yürürken görev başarı/başarısızlık örneklerinden online task policy çıkarımı
- canlı retry bütçesi güncellemesi
- approval-by-exception için canlı auto-approval önerileri
- yüz ve ses tanıma için canlı eşik güncellemesi
- apply / canary / shadow çalışma modu
- kalıcı durum dosyası: `data/learning/live_adaptive_learning_state.json`

## Yeni olaylar
- `learning.online_training.status`
- `learning.online_training.sample`
- `learning.online_training.result`
- `learning.online_model_state`
- `learning.online_policy_update`
- `learning.online_biometric_threshold_update`

## Beklenen etki
- başarılı ve düşük müdahaleli görevler daha fazla otomatik akışa yaklaşır
- zayıf görevler daha korumalı gating alır
- biyometrik eşikler sabit kalmaz, görülen örneklere göre online adapte olur
