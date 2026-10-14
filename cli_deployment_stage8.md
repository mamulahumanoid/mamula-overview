# CLI ve dağıtım — Aşama 8

Tam bir robot OS için **komut satırı**, **sürüm**, **konfigürasyon profilleri**, **sırlar**, **rollback** ve **field deploy** (systemd / konteyner / Jetson) birlikte düşünülür.

**İlgili:** `diagnostics_log_replay_stage7.md`, `lifecycle_manager_stage6.md`, `gateway_runtime_hardening_stage1.md`.

---

## CLI (`mamula`)

Giriş noktası: `pyproject.toml` → `mamula = core.tools.mamula_cli:main`. Geliştirme: `python -m core.tools.mamula_cli`.

| Komut | Açıklama |
|-------|----------|
| `mamula doctor` | Ortam, yollar, paket sürümü |
| `mamula doctor --physical-gates` | Fiziksel deneme öncesi on maddelik otomasyon (bkz. `scripts/verify_physical_readiness.sh`) |
| `mamula bringup-report` | Tek çıktıda doctor (`--strict`), validasyonlar, audit’ler, `test tier1` / **`test isaac`** / `hil` / `native`, hardware-protocol selftest, bus stress, `replay last-run` |
| `mamula validate-config` / `validate-topics` / `safety-audit` | Konfigürasyon ve topic şeması; güvenlik politikası özeti |
| `mamula skills audit` | Skill kataloğu doğrulama |
| `mamula validate-profile <name> --materialize` | Profil çözümü + materialize |
| `mamula test <tier>` | `tier1` … `tier5_robot` kümülatif; kısa adlar `hil` / `native` / **`isaac`** (`hil and not robot`, `native and not robot`, `(isaac or isaac_offline) and not robot`) |
| `mamula hardware-protocol selftest` | Donanım protokolü selftest |
| `mamula bus stress [unix_socket\|inproc]` | Bus yük/stres (`unix_socket` experimental; sandbox/CI içinde skip edebilir) |
| `mamula run profile <name>` | `HUMANOID_RUNTIME_PROFILE` ile `python -m core.run_app` (takma adlar `registry`) |
| `mamula skills list` | Yerel skill kataloğu (`robot_skill_catalog`) |
| `mamula drivers list` | Varsayılan HAL kaydı anahtarları |
| `mamula safety status` | Ops özeti (HTTP varsa) + kritik ortam değişkenleri |
| `mamula logs tail [-n]` | Son oturum JSONL dosyasının son satırları |
| `mamula logs filter [kind]` | Önceki süzgeç davranışı (safety, llm, …) |
| `mamula replay [last-failure]` | Varsayılan: son failure snapshot |
| `mamula replay session <jsonl>` | Oturum JSONL → `EventBus` (`--dry-run` ile deneme) |
| `mamula replay last-run` | Son oturum dosyası ile dry-run (bring-up raporunda kullanılır) |
| `mamula diagnostics` | Ops hardware telemetry JSON özeti |
| `mamula trace task <id>` | Reasoning SQLite trace |
| `mamula config validate` | `core/config/*.json` ayrıştırma kontrolü |
| `mamula update` | Paket güncelleme notları (operatör için metin) |
| `mamula rollback` | Önceki sürüme dönüş prosedürü (metin + pip örneği) |
| `mamula prefetch api-cache` | `FETCH_API` kaynaklı hava/wiki verilerini SQLite’a önceden yazar (`run_prefetch`, çevrimdışı kullanım); `--file` veya `MAMULA_PREFETCH_JSON` |
| `mamula bus daemon` | Merkezi olay bus döngüsü (`core/tools/bus_daemon.py`); varsayılan `unix_socket` + daemon modu ama transport experimental; `--socket-path`, `--poll-max-items`, `--sleep-ms` |

---

## Çevrimdışı API önbelleği (prefetch)

- **Amaç:** İnternet varken listelenen sorguları `api_skill_cache.db` ve bilgi için semantic facts’a almak; bağlantı kesilince `ApiSkillModule` bayat/`MAMULA_API_OFFLINE_STALE` ile yanıt (`prefetch_api_cache.py`).
- **Elle:** `python -m core.tools.prefetch_api_cache --file /path/to/list.json` veya `mamula prefetch api-cache --file …`
- **Zamanlama:** Örnek systemd birimleri `deploy/systemd/mamula-prefetch-api-cache.service` + `.timer` — varsayılan **günde 2 kez** (`06:00` ve `18:00`, ±5 dk rastgele gecikme). JSON yolu birim içinde `Environment=MAMULA_PREFETCH_JSON=/etc/mamula/offline_api_prefetch.json` ile verilir; `/etc/mamula/offline_api_prefetch.json` sahaya göre oluşturulur (örnek şema: `core/config/offline_api_prefetch.sample.json`).
- **Not:** Timer yalnızca **oneshot** servisi tetikler; runtime (`mamula-runtime`) ayrı kalır.

---

## Konfigürasyon profilleri

- Çözümleme sırası: `run_app` → `HUMANOID_RUNTIME_PROFILE` veya `CORE_RUNTIME_PROFILE` → `resolve_profile_alias` (`core/runtime/profiles/registry.py`).
- Örnek takma adlar: `hardware` → `embodied_real_hardware`, `sim` → `embodied`.
- Üretimde profili **systemd `Environment=`** veya Docker `ENV` ile sabitleyin.

---

## Sır yönetimi

| Ortam | Kullanım |
|-------|----------|
| `CORE_OPS_TOKEN` | Ops HTTP Bearer |
| `CONTROL_CORE_BRIDGE_BIN` | Native köprü yolu |
| systemd `EnvironmentFile=-/etc/mamula/secrets.env` | Önerilen: dosya izinleri 600, git’e koymayın |

Uygulama sırlarını repoya yazmayın; Jetson / sunucuda environment veya secrets manager kullanın.

---

## Sürüm ve rollback

- Paket sürümü: `pyproject.toml` → `[project] version`.
- `mamula doctor` ve `mamula update` metni bu sürümü gösterir.
- Rollback: önceki wheel / commit ile `pip install humanoid-core==X.Y.Z` veya kontrol edilen sanal ortam geri yükleme; systemd `ExecStart` yolu sabit kalmalı.

---

## systemd

Örnek birim: `deploy/systemd/mamula-runtime.service`. `WorkingDirectory` ve sanal ortam yolunu sahaya göre düzenleyin.

API önbellek zamanlayıcısı: `deploy/systemd/mamula-prefetch-api-cache.service` ve `mamula-prefetch-api-cache.timer` (bkz. üstte «Çevrimdışı API önbelleği»).

Merkezi bus: `deploy/systemd/mamula-bus-daemon.service` — `RuntimeDirectory=mamula`, soket `/run/mamula/bus.sock`; istemci süreçlerde `HUMANOID_BUS_TRANSPORT=unix_socket`, `HUMANOID_BUS_UNIX_MODE=client`, `HUMANOID_BUS_UNIX_PATH=/run/mamula/bus.sock`. Bu yol bugün **experimental** kabul edilir; kritik kontrol/QoS için production broker yerine geçmez.

---

## Docker

Örnek: `deploy/docker/Dockerfile` — üretim imajı için çok aşamalı derleme ve native köprü katmanını genişletin.

### CI: imaj yayınlama ve imzalama

- **İş akışı:** `.github/workflows/docker-publish.yml` — `v*` tag push veya **workflow_dispatch** ile `deploy/docker/Dockerfile` derlenir, **GHCR** (`ghcr.io/<owner>/<repo>`) üzerine gönderilir ve **Cosign** ile imza digest’e yazılır (GitHub **OIDC**, repoda özel anahtar tutulmaz).
- **Etiketler:** semver tag’de `latest` + sürüm etiketleri; dal/manuel çalıştırmada en azından `sha-<git>` digest etiketi üretilir (`docker/metadata-action`).
- **Sahada doğrulama (isteğe bağlı):** `cosign verify <ghcr.io/.../...@sha256:...> --certificate-identity-regexp ...` — Sigstore/Cosign belgelerindeki güncel bayraklar kullanılmalıdır.
- **Otomatik güncelleme:** Konteyner ortamında yaygın seçenekler: sabit digest ile yeniden `docker pull` + yeniden başlatma (systemd `ExecStartPre=-/usr/bin/docker pull …` veya orkestrasyon yeniden dağıtımı); isteğe bağlı yan süreçler (ör. Renovate/Dependabot imaj PR’ları, özel güncelleme ajanı) kurum politikasına göre eklenir. Python paket düzeyinde `mamula update`/`pip` ile çekirdek güncellemesi ayrı kalır.

---

## NVIDIA Jetson

Özet: `deploy/jetson/README.md` — ARM64, CUDA/TensorRT isteğe bağlı; ses için host cihaz mount; gerçek zamanlı için CPU governor ve izolasyon politikası sahaya özeldir.

---

## Aşama 8 kabul ölçütleri

- [x] Tek `mamula` giriş noktası ile doctor / run profile / listeler / günlük / config doğrulama.
- [x] `mamula bringup-report`, `mamula doctor --physical-gates`, `mamula test` tier / `hil` / `native` semantiği ve ilgili betikler (`verify_physical_readiness.sh`) dokümante.
- [x] Dağıtım için systemd + Docker + Jetson notları depoda.
- [x] Üretim CI imaj imzalama ve otomatik güncelleme: GHCR + Cosign (`docker-publish.yml`); sahada güncelleme kalıpları yukarıda «Docker» altında.
