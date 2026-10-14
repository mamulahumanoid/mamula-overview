# MAMULA

**MAMULA**, ev ve benzeri ortamlarda görev alabilen bir **insansı robot** için geliştirilen yazılım çekirdeğinin (runtime) kaynak kodudur. Bu depo (`humanoid_core`), robotun algı, planlama, hareket, manipülasyon ve güvenlik katmanlarını tek bir mimaride birleştirir.

## MAMULA nedir?

- **İnsansı form faktörü** hedeflenir: iki ayak üzerinde denge, yürüme ve duruş; kollar ile nesne alıp götürme, ev içi görevlere uygun davranışlar.
- Yazılım, **simülasyon** (ör. NVIDIA Isaac Sim ile locomotion ve düşme–kalkış senaryoları) ile **gerçek donanım / HIL** (güvenli komut kaydı ve gete katmanları) arasında aynı komut sözleşmesini kullanacak şekilde tasarlanmıştır.
- **Ses ve doğal dil** üzerinden hedef üretimi, görev grafiği ve yürütme (executive) ile bağlanabilir; bellek, görev planlayıcı ve eylem yönlendirici modüller içerir.

### Yerel-öncelikli sohbet ve hafıza

MAMULA bir bulut sohbet platformu değil, ev içinde çalışan yerel-öncelikli bir
humanoid robottur. Temel sohbet, hazır yerel modelle çıkarım ve izin verilmiş
yerel hafıza işlemleri internet bağlantısı gerektirmez. Ağ kesildiğinde hava
durumu gibi belirli bir ağ servisi kullanılamayabilir; bu durum temel sohbeti,
yerel komutları, güvenliği veya yerel hafızayı devre dışı bırakmaz.

Kullanıcıya dönük Türkçe metinde konuşma akışı için **sohbet** denir.
`session_id` gibi teknik alanlar yalnızca geriye uyumlu iç kimliklerdir. Kalıcı
hafıza yerel olsa da açık rıza, amaç, saklama süresi, kaynak ve kullanıcı
izolasyonu kuralları devam eder; bir kaydın gerçekten okunduğu veya yazıldığı
yalnızca çalışma zamanı kanıtıyla söylenir. Normatif sözleşme:
[`core/contract/local_first_chat_v1.py`](core/contract/local_first_chat_v1.py).

İzin verilen yerel TXT/Markdown/JSON/JSONL/CSV/HTML/PDF belgeleri için ağsız,
kaynak gösterimli **Local RAG v1** katmanı da bulunur. SQLite FTS5 çekirdeği ek
paket istemez; PDF ve isteğe bağlı Qwen3 dense embedding desteği `rag` extra'sı
ile kurulur. İşletim ve güvenlik sınırları:
[`core/docs/local_rag_v1.md`](core/docs/local_rag_v1.md).

Local RAG üzerindeki **MAMULA Research v1**, bir soruyu birden fazla yerel
kaynakta araştırır; her iddiayı citation/hash ile bağlar, maddi çelişkileri
sessizce çözmek yerine işaretler ve kanıt yetersizse çekimser kalır. Sözleşme
ve qualification komutları:
[`core/docs/local_research_v1.md`](core/docs/local_research_v1.md).

Geliştirici tarafındaki **MAMULA Code Expert v1**, Python kaynaklarını
çalıştırmadan AST ile indeksler; sembol tanımlarını, çağrı noktalarını,
bağımlıları ve ilişkili testleri göreli yol/satır/SHA-256 kanıtıyla raporlar.
Belirsiz sembollerde ve yetersiz kanıtta fail-closed kalır; otomatik kod veya
runtime değişikliği yapmaz. Kullanım ve qualification:
[`core/docs/code_expert_v1.md`](core/docs/code_expert_v1.md).

Qualified Qwen3.6 adapter'ı için **GRPO/RLVR v1 readiness** katmanı da model
çıktısını çalıştırmadan exact/numeric/choice/JSON verifier reward'ları, grup
relative advantage, immutable dataset hash'leri ve H100 preflight üretir.
Qualification holdout eğitimden ayrı kalır ve hiçbir sonuç runtime'a otomatik
bağlanmaz. Ayrıntı: [`core/docs/qwen_grpo_rlvr_v1.md`](core/docs/qwen_grpo_rlvr_v1.md).

## Neler yapabilir? (özet)

- Ev içi anlamlı görevler için modül seti (temizlik, mutfak, çamaşır, cihaz etkileşimi vb. semantik katmanlar).
- Lokomosyon denetimi, denge, düşme riski ve kurtarma senaryolarıyla uyumlu durum temsili.
- Isaac Sim ile **yürüyüş ve stabilite** testleri; oturum köprüsü ile açık simülasyon oturumuna komut gönderme.
- Gerçek robot veya tezgâh için **güvenli komut günlüğü** ve şema doğrulamalı adapter katmanı.

> Not: Her özellik üretim olgunluğunda olmayabilir; bazı akışlar simülasyon veya test profilleriyle sınırlıdır. Ayrıntılı teknik davranış için `core/docs/` altındaki sözleşme dokümanlarına bakın.

## 10 dakikada ilk çalıştırma (onboarding)

Bu bölüm, projeyi ilk kez açan birinin "çalışıyor mu?" sorusuna hızlı cevap vermesi için hazırlanmıştır.

### 1) Kurulum (ürünleşme — core gate)

Başka makinede core gate:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

| Extra | İçerik |
|-------|--------|
| *(base)* | `requests` — minimal runtime |
| `sim` | `numpy`, `scipy`, `matplotlib`, `mujoco` |
| `web` | `flask` — HTTP adapters |
| `hardware` | `pyserial` |
| `voice` / `vision` / `learning` | STT / YOLO / PyTorch eğitim |
| `qwen-training` | İzole Qwen3.6 QLoRA uyumluluk aralıkları; gerçek koşu hash-lock gerektirir |
| `rag` | Local RAG PDF ve isteğe bağlı Qwen3 embedding desteği; lexical çekirdek extrasızdır |
| `dev` | `pytest`, `pytest-cov`, `ruff`, `mypy`, `PyYAML` |

Varsayılan `pytest` = **core gate**: çekirdek sözleşme + güvenlik; web, vision, sim, HIL/hardware, native ve robot testleri marker/extra ile ayrıdır. Geliştirici araçları için `pip install -e ".[dev]"`; profil testleri: `mamula test core|sim|hil|hardware|native` veya `pytest -m web|vision|sim|hil|hardware|native`. **Public demo kanıtı:** `mamula demo-replay` ([`docs/DEMO_REPLAY_EVIDENCE.md`](docs/DEMO_REPLAY_EVIDENCE.md)). **Sim / domestic / Isaac demosu (tek sıra):** [`docs/SIM_QUICKSTART.md`](docs/SIM_QUICKSTART.md) — önce `source scripts/env/isaac_docker.env.sh` (+ gazebo). **Kalite kapıları:** [`docs/QUALITY_GATES.md`](docs/QUALITY_GATES.md). Modül olgunluk: [`docs/MODULE_READINESS.md`](docs/MODULE_READINESS.md). Ayrıntı: [`tests/README.md`](tests/README.md).

Qwen3.6-27B çok dilli QLoRA hattı, fail-closed veri/template/environment
kapıları ve gerçek H100 kanıt sınırı için [`training/qwen36/README.md`](training/qwen36/README.md).

Ayrıntı ve dizin eşlemesi (`core/` = kaynak paketi): [`docs/PRODUCT_RELEASE.md`](docs/PRODUCT_RELEASE.md).

### Public repo belgeleri

Bu depo Apache-2.0 lisansı ile yayımlanır: [`LICENSE`](LICENSE). Katkı, güvenlik, gizlilik ve model/veri kuralları:

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`SECURITY.md`](SECURITY.md)
- [`PRIVACY.md`](PRIVACY.md)
- [`MODEL_AND_DATA_POLICY.md`](MODEL_AND_DATA_POLICY.md)
- [`PUBLIC_API.md`](PUBLIC_API.md)
- [`CHANGELOG.md`](CHANGELOG.md)
- [`docs/RELEASE_NOTES_0.4.0.md`](docs/RELEASE_NOTES_0.4.0.md)
- [`docs/DEPRECATION_POLICY.md`](docs/DEPRECATION_POLICY.md)
- [`docs/RELEASE_PROCESS.md`](docs/RELEASE_PROCESS.md)
- [`core/docs/skill_maturity_v1.md`](core/docs/skill_maturity_v1.md)

Özellikle AI hafıza, ses/görüntü, fiziksel robot telemetrisi, model ağırlıkları ve learning artifact dosyaları public issue/PR veya kaynak repoya eklenmemelidir.

Public Python API bilinçli olarak dardır: dış geliştiriciler `core.contract.*`, `core.bus.*` ve `core.skills.sdk` yüzeylerine güvenebilir; `core.modules.*`, `core.brain.*`, `core.learning.*` gibi paketler internal/experimental kabul edilir. Skill katalog olgunluğu da ayrı izlenir: public sürümde yalnız `mvp_hardened` skill’ler destek vaadidir; diğerleri `experimental` veya `catalog_only` olarak işaretlenir.

### Kaynak arşivi (temiz dağıtım paketi)

Ana paketten **çıkarılanlar:** `.git/`, `__pycache__/`, `runtime/`, loglar, geçici `.db`, build çıktıları, önbellekler, `models/`, `third_party_models/`, `checkpoints/`, büyük `artifacts/`. Küçük test fixture’ları (`data/benchmarks/*.json`) arşivde kalır.

```bash
./scripts/package_source_release.sh humanoid_core_source.tar.gz
SOURCE_RELEASE_WARN_MB=8 SOURCE_RELEASE_MAX_SIZE_MB=25 ./scripts/package_source_release.sh humanoid_core_source.tar.gz
./scripts/verify_product_bootstrap.sh
# İzlenmeyen ağaç: PACKAGE_MODE=worktree ./scripts/package_source_release.sh humanoid_core_worktree.tar.gz
```

Modeller için ayrı tarball: `models/`, `third_party_models/`, `checkpoints/` (bkz. `models/README.md`).

Pardus (Debian tabanlı) için sistem paketleri:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip build-essential cmake ninja-build git curl
```

### 2) Hızlı güven kontrolü

```bash
python -m pytest core/tests -q
```

Beklenen: testlerin çoğu geçer; bu adım temel bağımlılıkların ve Python ortamının doğru olduğunu gösterir.

**Tek bring-up raporu:** `mamula bringup-report` — doctor (`--strict`), `validate-config`, `validate-topics`, `safety-audit`, `skills audit`, `validate-profile production_supervised --materialize`, `test core` / **`test isaac`** / `test hil` / `test native`, `hardware-protocol selftest`, `bus stress unix_socket`, `replay last-run`. Alt komutlar ayrı ayrı da çalıştırılabilir.

**`mamula test` profilleri:** `core` varsayılan `pytest` core gate ile aynı seçimdir. `hil` ve `native` yalnızca ilgili pytest marker’larını seçer (`hil and not robot`, `native and not robot`); legacy kümülatif tier adları (`tier3_hil`, `tier4_native`) ayrıca desteklenir. **`mamula test isaac`** `(isaac or isaac_offline) and not robot` seçer. **CI** (`CI=true` veya GitHub Actions): `HUMANOID_RUN_ISAAC` varsayılan **1** (`conftest` + workflow job env); Isaac Python yoksa subprocess testleri fixture’da skip edilir — kapatmak için `HUMANOID_RUN_ISAAC=0`. CI `test-tiers` workflow’unda **core**, **hil**, **native**, **learning**, **extended-scenarios** ve **isaac** job’larında da aynı env tanımlıdır. **isaac** job’ı önce `pytest -m isaac_offline`, sonra `pytest -m isaac` çalıştırır.

**Fiziksel deneme öncesi:** `./scripts/verify_physical_readiness.sh` veya `mamula doctor --physical-gates` (on maddelik otomasyon + doctor).

**Kaynak arşivi boyutu:** `SOURCE_RELEASE_WARN_MB` / `SOURCE_RELEASE_MAX_SIZE_MB` — `scripts/package_source_release.sh` üst bilgisine bakın.

> Runtime state dizinleri ve DB path politikası için: `core/docs/runtime_state.md`.

### 3) Uygulamayı ayağa kaldırma (runtime)

```bash
python -m core.app --profile s422_light --no-http-router
```

Ne olur?

- `EventBus` + `Runtime` başlar.
- Seçilen profile göre modüller bootstrap edilir.
- `world.state` ve ilgili locomotion/perception topic’leri akmaya başlar.

> İpucu: `s422_light` başlangıç için iyi bir profildir; tam zincire göre daha hızlı debug edilir.

### 4) Sözleşme seviyesinde doğrulama

İlk kontrol için odak:

- `world.state.scene.objects`
- `world.state.scene.terrain_model`
- `world.state.scene.terrain_height_map`
- `robot.physical_state`

Bu alanlar, projedeki planlama + fiziksel kontrol ayrımını anlamanın en hızlı yoludur.

### 5) İlk katkı akışı (önerilen)

1. Küçük bir modül veya sözleşme değişikliği yap.
2. İlgili hedef test dosyasını çalıştır.
3. Domain filtresiyle genişlet (`-k isaac` gibi).
4. Son olarak `core/tests` tam paketini koş.

## Teknik mimari (özet)

| Bileşen | Rol |
|--------|-----|
| **EventBus** (`core/bus/event_bus.py`) | Süreç içi olay kuyruğu: `publish` ile mesaj eklenir, `poll` ile abonelere deterministik dağıtım. |
| **Runtime** (`core/runtime/runtime.py`) | Modül tikleri ve izleme (heartbeat / beat). |

`EventBus` API public/stable olsa da transport olgunluğu ayrıdır: `inproc` stable, `file_replay` beta, `unix_socket` experimental. UNIX soket modunda `HUMANOID_BUS_UNIX_MODE=client` iken istemci, daemon soketi oluşana kadar en fazla **`HUMANOID_BUS_UNIX_DAEMON_WAIT_S`** saniye bekler (varsayılan **5**; değer **0.5–60** arasında sıkıştırılır). Subscribe ACK bekleme süresi **`HUMANOID_BUS_UNIX_SUBSCRIBE_ACK_TIMEOUT_S`** ile ayarlanır (varsayılan **0.25**; değer **0–3** arası). Restricted sandbox/CI ortamlarında AF_UNIX datagram testleri açık skip edebilir. Detay: `core/docs/distributed_transport_v1.md`.
| **RuntimeBootstrap** (`core/runtime/bootstrap.py`) | Profil adından modül listesi üretir, ör. `ExecutiveBridgeModule`, `hardware_bridge`, `locomotion_bringup` vb. sırayla örnekler ve `bus.subscribe` bağlar. |
| **create_app** (`core/app.py`) | `EventBus` + `Runtime` + `attach_profile(...)`; HTTP ses yönlendiricisi isteğe bağlı. |

Yürütme hattı kabaca: üst katmanlar **`executive.action`** yayınlar → **ExecutiveBridge** (ve gete modülleri) fiziksel eylemleri **`RobotBodyAPI`** üzerinden `RealRobotAdapter` / `SimRobotAdapter` ile sonuçlandırır → **`executive.action_result`** ile geri bildirim.

## World Model ve durum sözleşmeleri

Bu depoda iki katman birlikte çalışır:

1. **World Model (`world.state`)**  
   Görev planlama, bağlamsal karar ve sorgu için hızlı/özet blackboard.
2. **Robot Physical State (`robot.physical_state`)**  
   Humanoid lokomosyon ve recovery için kanonik, ayrıntılı fiziksel durum sözleşmesi.

Bu ayrım özellikle önemlidir: `world.state` her şeyi kopyalamaz; robotun derin fiziksel durumu
`robot.physical_state` tarafında kanonik kalır.

### `world.state.scene` (algı + çevre)

`world.state.scene` içinde başlıca alanlar:

- **`objects`** (`objects_schema_version = wm.scene.objects.v4`)  
  Algılanan semantik nesneler. Her nesnede tipik olarak:
  - `object_id`
  - `semantic_label`
  - `pose`
  - `affordances` (hızlı isim listesi: `grasp`, `pour`, ...)
  - `affordance_models` (manipülasyon için yapılandırılmış içerik: `grasp_points`, `hand_type`,
    `approach_vector`, `tilt_axis`, `tilt_angle_deg`, vb.)
  - `uncertainty`, `kinematics`, `lifecycle`, `visibility`, `temporal_history`

- **`terrain_model`** (`terrain_model_schema_version = wm.terrain_model.v1`)  
  Humanoid yürüyüş için temas/zemin yüzeyleri listesi:
  - `surface_id`, `type`, `pose`, `normal`, `friction`, `walkable`, `slope`
  - ek olarak: `area`, `roughness`, `step_height`, `contact_points`

- **`terrain_height_map`**  
  Düzenli grid veya patch tabanlı arazi bilgisi:
  - `height_grid[row][col] -> z`
  - `grid_shape`, `cell_size_m`, `origin_m`
  - `patches` (varsa)

- **`terrain_summary`**  
  Planlayıcı/gait için özet metrikler:
  - `max_slope_deg`, `max_roughness`, `max_height_delta_m`
  - `recommended_speed_scale`
  - `terrain_mode` (`flat`, `uneven`, `sloped`, `stairs_or_steep`)

- **`contact_state`**  
  `locomotion.contact_state` akışından gelen temas özeti (zaman damgası ile).

### `robot.physical_state` (kanonik fiziksel durum)

Humanoid denge/yürüme için detaylı kaynak **`robot.physical_state`** topic’idir (bkz.
`core/docs/robot_physical_state_v1.md`).  
Bu sözleşme `state_estimation`, `support`, `contact`, `gait`, `balance`, `recovery` gibi
alt bölümlerde pose/velocity/CoP/support polygon/contact vb. verileri taşır.

World model bu katmanı birebir çoğaltmaz; böylece tek doğruluk kaynağı korunur.

### `world.query` ile pratik erişim

`WorldModelModule`, query kolaylığı için `robot.physical_state` üzerinde read-through bridge sağlar:

- `q = "robot.physical_state"` → son kanonik payload
- `q = "robot.physical_state.state_estimation.position_m.x"` → derin alan erişimi

Bu köprü, veri modelini çoğaltmadan üst katmanların tek sorgu API’siyle bilgi almasını sağlar.

#### `world.query` örnek istek/yanıt

Basit pozisyon sorgusu:

```json
{
  "topic": "world.query",
  "payload": {
    "q": "robot.physical_state.state_estimation.position_m",
    "reply_topic": "world.query.result"
  }
}
```

Örnek yanıt:

```json
{
  "query": "robot.physical_state.state_estimation.position_m",
  "result": { "x": 0.14, "y": -0.03, "z": 0.91 },
  "timestamp": 1760000000.12
}
```

Arazi özeti sorgusu:

```json
{
  "topic": "world.query",
  "payload": {
    "q": "scene.terrain_summary.recommended_speed_scale"
  }
}
```

> Not: `result = null` geliyorsa yol mevcut değildir veya henüz veri üretilmemiştir.

### Neden bu yapı?

- **Planlama kolaylığı**: `world.state` hızlı karar yüzeyi sunar.
- **Fiziksel doğruluk**: düşük seviye humanoid kontrol sözleşmesi (`robot.physical_state`) ayrık kalır.
- **Bakım kolaylığı**: tek isim / tek kaynak ilkesiyle şema çakışmaları azalır.
- **Sim ve gerçek uyumu**: Isaac/HIL akışları aynı sözleşmelere bağlanır.

## Dizin yapısı

| Yol | İçerik |
|-----|--------|
| `core/modules/` | Davranış modülleri: `execution/`, `robot/` (Isaac köprüleri, gerçek robot, QP, denge, vb.), `action_router_module`, `memory_*`, … |
| `core/runtime/` | Profil üreticileri ve bootstrap sırası. |
| `native/control_core/` | C++ low-level çekirdek iskeleti (CMake, `control_core_bridge`); Python ile sınır: `core/docs/control_plane_python_vs_native.md`; Aşama 5 bileşen haritası: `core/docs/real_time_control_core_stage5.md`. |
| `core/tools/` | CLI, Isaac senaryo koşturucuları ve benchmark/pipeline araçları (`run_isaac_*`, `sim_campaign_launcher.py`, `run_full_sim_learning_pipeline.py`, `run_multi_seed_sim_learning_campaign.py`, …). |
| `core/docs/` | `architecture_index.md` ile mimari özet; alt sistem sözleşmeleri (`*_v1.md`); `topic_atlas.md`; Python/native kontrol düzlemi (`control_plane_python_vs_native.md`); C++ geçiş planı (`cpp_low_level_migration_v1.md`); gerçek zamanlı çekirdek Aşama 5 (`real_time_control_core_stage5.md`); CLI/dağıtım Aşama 8 (`cli_deployment_stage8.md`). |
| `deploy/` | Örnek systemd (`systemd/mamula-runtime.service`), Docker (`docker/Dockerfile`), Jetson (`jetson/README.md`). |
| `core/config/` | Örn. 28-DoF eklem şeması (`joints_schema_28.json`) ve runtime/robot konfigürasyon dosyaları. |
| `tests/`, `core/tests/` | Pytest koleksiyonu (`pytest.ini` → `testpaths`). |

## Profiller (örnekler)

Profiller `RuntimeBootstrap.PROFILE_BUILDERS` ve takma adlarla (`s421`, `s422`, …) çözülür. Örnekler:

- **`s421` / `embodied_standing_bringup`**: Ayakta duruş / harness gete zinciri.
- **`s422` / `embodied_turn_walk_hil`**: Dönüş ve yürüme HIL; çok modül → yoğun bus trafiği.
- **`s422_light` / `embodied_turn_walk_hil_light`**: Aynı lokomosyon geteleri + süpervizör, gait/MPC fan-out olmadan (entegrasyon testleri için).

Tam liste: `bootstrap.supported_profiles()` veya `core/runtime/bootstrap.py` içi `PROFILE_BUILDERS`.

Profil seçimi için kısa rehber:

- **Yeni modül geliştirirken**: önce hafif profil (`*_light`) ile başlayın; debug döngüsü daha hızlıdır.
- **Lokomosyon davranışı doğrularken**: `s422` benzeri tam zincirleri tercih edin.
- **Donanım/HIL bağlamında**: safety gate ve command log bileşenlerinin aktif olduğu profili kullanın.

Pratik kontrol akışı:

1. Profili ayağa kaldır.
2. `world.state` ve `robot.physical_state` yayınlarının aktığını doğrula.
3. Hedef davranış topic’lerini (`executive.action`, `executive.action_result`, `locomotion.*`) gözlemle.
4. Sonra geniş entegrasyon testlerine geç.

## Robot API ve adapter’lar

- **`RobotBodyAPI`**: Soyut gövde arayüzü (konuşma, gidis, pick/place, yürüme, …).
- **`SimRobotAdapter`**: Bellek içi durum; e2e ve birim testlerde hızlı doğrulama.
- **`RealRobotAdapter`**: Eklem şeması doğrulama, `data/hardware/real_robot_commands.jsonl` gibi güvenli komut günlüğü; telemetri tazeliği ve gete koşulları.

Canonical MAMULA mekanizması **28 bağımsız servo/eklem ekseni** kullanır. Her
bacakta `hip_yaw`, `hip_roll`, `hip_pitch`, `knee_pitch`, `ankle_pitch` ve
`ankle_roll` bulunur. Tek kaynaklar:

- fiziksel mekanizma, limitler ve transmission bilgisi:
  `core/models/mamula_humanoid.urdf`
- public isim ve sıra sözleşmesi: `core/config/joints_schema_28.json`
- vendor isim→node eşlemesi: `core/config/vendor_servo_bus_map.json`

Yeni ankle-roll servoları mevcut 1–26 saha node kimliklerini değiştirmemek için
`l_ankle_roll=27` ve `r_ankle_roll=28` olarak atanmıştır. Gerçek ilk-adım kapısı,
iki yeni eksen dahil 12 bacak ekleminin calibration, zero ve homing kanıtı
olmadan açılmaz.

Gerçek robotta önerilen geçiş sırası (shadow → HIL → bench → düşük hızlı gözetimli → sınırlı otonom görev → tam), shadow günlük dosyası ve `MAMULA_HARDWARE_SHADOW_COMMANDS` ortam değişkeni için: [`core/docs/real_robot_shadow_transition_v1.md`](core/docs/real_robot_shadow_transition_v1.md). Hareketli robota bağlanmadan önce minimum koşullar: [`core/docs/real_robot_minimum_readiness_checklist_v1.md`](core/docs/real_robot_minimum_readiness_checklist_v1.md). İlgili pytest paketlerini toplu koşturmak için: `./scripts/verify_robot_readiness.sh` (opsiyonel `--core`). Fiziksel deneme öncesi otomasyon: `./scripts/verify_physical_readiness.sh` veya `mamula doctor --physical-gates`; geniş bring-up: `mamula bringup-report`.

Adapter seçimi için pratik öneri:

- **İş kuralı / planlama / routing** geliştiriyorsanız önce `SimRobotAdapter` kullanın.
- **Donanım sınırları / güvenlik davranışı** doğruluyorsanız `RealRobotAdapter` yoluna geçin.
- Yeni bir capability eklerken `RobotBodyAPI` sözleşmesini önce netleştirip, sonra iki adapter’da da
  aynı semantik sonucu üretmeye dikkat edin.

Beklenen disiplin:

- API seviyesinde tek komut anlamı,
- adapter seviyesinde ortama özgü uygulama,
- üst katmanlarda adapter farkından bağımsız davranış.

## NVIDIA Isaac Sim (araçlar)

**Hızlı başlangıç:** [`docs/SIM_QUICKSTART.md`](docs/SIM_QUICKSTART.md) (`source scripts/env/…` → `mamula sim` → domestic-sim → ürün demosu).

Araçlar `core/tools/` altında; Isaac alt süreçleri `ISAAC_PYTHON` değişkeni veya platform varsayılanı ile açılır.

- Linux/Pardus tipik örnek: `export ISAAC_PYTHON=/opt/isaac-sim/python.sh`
- Windows tipik örnek: `set ISAAC_PYTHON=C:\isaacsim\python.bat`

**Pardus’ta Isaac kuruluysa:** Kurulum yolunuz farklıysa `ISAAC_PYTHON` mutlaka ayarlayın; aksi halde kod sırayla şu dosyalara bakar: `/opt/isaac-sim/python.sh`, `$HOME/isaac-sim/python.sh`, `$HOME/IsaacSim/python.sh`. Yerelde gerçek Isaac alt süreçli pytest için (CI dışında): `export HUMANOID_RUN_ISAAC=1`. Hızlı doğrulama: `python3 -m core.tools.isaac_sim_workflow --validate-python`. Isaac köprü yolu için `core/config/isaac_sim_bridge_v1.json` içindeki `isaac_root` veya `ISAAC_SIM_ROOT` ortam değişkenini kullanın. Test paketi: `mamula test isaac` veya `python3 -m pytest core/tests/test_isaac_subprocess_integration.py -m isaac -q`.

**NVIDIA / Vulkan (konteyner veya host’tan lib/ICD bağlama):** Isaac veya Vulkan tabanlı sim, sürücü kütüphanelerini bulamazsa `LD_LIBRARY_PATH` ve Vulkan ICD yolunu ayarlayın; dizinler kurulumunuza göre değişir. Örnek (yolları kendi bind-mount’larınıza uyarlayın):

```bash
export LD_LIBRARY_PATH=/nvidia-extra:/usr/local/nvidia/lib:/usr/local/nvidia/lib64:$LD_LIBRARY_PATH
export VK_ICD_FILENAMES=/host-icd/nvidia_icd.json
```

**Pardus + Docker + WebRTC (aynı makineden bağlantı):** `127.0.0.1` / `8211`, `docker ps`, `nvidia-smi` ve konteyner içi `export` adımlarının tamamı: [`core/docs/isaac_sim_docker_pardus_webrtc.md`](core/docs/isaac_sim_docker_pardus_webrtc.md).

## Gazebo ve MuJoCo (sim platformları)

İkinci ve üçüncü fizik motoru yüzeyi Isaac ile aynı katmanda: **offline** köprü/workflow testleri her PR’da; **subprocess** testleri kurulum varsa koşar (`HUMANOID_RUN_GAZEBO=1` / `HUMANOID_RUN_MUJOCO=1`).

| Platform | Ortam | Doğrulama | Test paketi |
|----------|--------|-----------|-------------|
| Gazebo | `GAZEBO_CMD=gz` (veya `gazebo`) | `python3 -m core.tools.gazebo_sim_workflow --validate-cmd` | `mamula test gazebo -v` |
| MuJoCo | `MUJOCO_PYTHON=python3` (mujoco pip) | `python3 -m core.tools.mujoco_sim_workflow --validate-python` | `mamula test mujoco -v` |

Köprü konfigürasyonu: `core/config/gazebo_sim_bridge_v1.json`, `core/config/mujoco_sim_bridge_v1.json`. Bus köprü modülleri: `gazebo_sim_bridge_module`, `mujoco_sim_bridge_module` (`gazebo.bridge.*` / `mujoco.bridge.*` topic’leri).

MuJoCo dört yönlü düşme–kalkma qualification testi, her yönde en az
0.60 saniye kesintisiz sıfır pelvis desteği ile diklik ve ayak destek-poligonu
marjlarını birlikte doğrular:

```bash
HUMANOID_RUN_MUJOCO=1 python -m pytest -q -m mujoco \
  core/tests/test_mujoco_domestic_subprocess_integration.py::test_mujoco_fall_recovery_subprocess_suite
```

Bu sonuç fizik simülasyonu kanıtıdır; fiziksel robot/HIL kabulü yerine geçmez.
Detaylı kapılar: [`docs/LOCOMOTION_CONTROL_QUALIFICATION.md`](docs/LOCOMOTION_CONTROL_QUALIFICATION.md).

Kapalı çevrim lokomosyon qualification kampanyası 18 deterministik P0/P1
fizik vakasını çalıştırır ve bağımsız gate ile doğrulanır:

```bash
python -m core.tools.mujoco_closed_loop_locomotion --campaign \
  --native-backend ctypes --output locomotion-campaign.json
python -m core.tools.locomotion_physics_qualification_gate \
  --input locomotion-campaign.json --out locomotion-qualification.json
```

Gate; 3B yürüyüş/yön değiştirme, push recovery, terrain, sensör
gecikmesi/kaybı, aktüatör doyumu, kütle-atalet uyumsuzluğu, payload ve kol
hareketi vakalarının tamamını fail-closed değerlendirir.

| Amaç | Modül / komut |
|------|----------------|
| Lokomosyon suite (headless) | `python -m core.tools.run_isaac_locomotion_stability_suite --report-out <json> --headless` |
| Düşme–kalkış (4 yön, headless) | `python -m core.tools.run_isaac_fall_recovery_direction_suite --report-out <json> --headless` |
| Açık GUI oturum köprüsü | `python -m core.tools.run_isaac_open_session_command --command connect\|locomotion\|status --bridge-root data/isaac_session_bridge` |
| GUI runtime harness | `python -m core.tools.run_isaac_gui_runtime_session --report-out <json> --command short_walk --bridge-root ...` |
| Semantic navigation regression / release gate | `python -m core.tools.sim_campaign_launcher --template semantic_navigation_regression --repeat-count 1 --campaign-name nav_gate_probe --report-out <json>` |
| Full sim-learning pipeline | `python -m core.tools.run_full_sim_learning_pipeline --template semantic_navigation_regression --repeat-count 1 --campaign-name nav_pipeline --report-out <json>` |
| Multi-seed sim-learning leaderboard | `python -m core.tools.run_multi_seed_sim_learning_campaign --template semantic_navigation_regression --repeat-count 1 --campaign-name nav_multi --seeds 11 17 --report-out <json>` |

Sahne betiği örneği: `core/tools/isaac_locomotion_scene.py` (vaka: `stand_balance`, `short_walk`, `turn_and_stop`, `disturbance_recovery`).

**Public demo kanıtı:** [`docs/DEMO_REPLAY_EVIDENCE.md`](docs/DEMO_REPLAY_EVIDENCE.md) — `mamula demo-replay` ile voice command -> planner -> skill -> safety gate -> native preview/control -> replay report. **Ürün demosu (dış gösterim):** [`docs/ISAAC_SAFE_CONTROL_PRODUCT_DEMO.md`](docs/ISAAC_SAFE_CONTROL_PRODUCT_DEMO.md) — önce [`docs/SIM_QUICKSTART.md`](docs/SIM_QUICKSTART.md) §5. `./scripts/run_isaac_safe_control_product_demo.sh`

Isaac ile çalışırken önerilen sıra:

1. Önce headless suite (`run_isaac_locomotion_stability_suite`) ile regresyon alın.
2. Sonra açık oturum köprüsü ile (`run_isaac_open_session_command`) interaktif doğrulama yapın.
3. GUI runtime harness ile belirli komut sekanslarını raporlayın.

Semantic navigation benchmark akışında önemli çıktı alanları:

- `summary.navigation_metrics_summary`
- `summary.navigation_gate_result`
- `release_gate_summary`

`semantic_navigation_regression` için `release_gate_summary.release_gate_status`
alanı `pass` / `fail` / `not_applicable` değerini verir. Üst pipeline araçları bu alanı
top-level rapora da taşır; böylece kampanya JSON’unu derin açmadan release readiness okunabilir.

Sık görülen entegrasyon hataları:

- `--bridge-root` yollarının uyuşmaması,
- Isaac tarafı açıkken farklı Python ortamı kullanılması,
- beklenen topic’lere publish var ama `poll` / runtime tick döngüsünün ilerlememesi.

## Testler

```bash
python -m pytest
python -m pytest core/tests -k isaac -q
# Isaac: Sim gerektirmeyen paket (CI ile aynı öncelik)
python -m pytest -m isaac_offline -q
# veya: mamula test isaac   →  (isaac or isaac_offline) and not robot; Sim suite için HUMANOID_RUN_ISAAC=1
```

- **`e2e_regression`**: Ses→hedef→eylem zinciri; örn. `python -m core.tools.e2e_regression --case navigation_and_task` (mutfak + “su getir” sim akışı, `SimRobotAdapter`).

Önerilen test stratejisi (hızlıdan pahalıya):

1. **Hedef dosya testleri**  
   Değiştirdiğiniz modül/test dosyalarını önce tek tek çalıştırın.
2. **Domain filtresi**  
   Isaac köprü / sahne betikleri için önce `pytest -m isaac_offline` veya `mamula test isaac`; gerçek Sim alt süreci için `HUMANOID_RUN_ISAAC=1` ve `ISAAC_PYTHON` (bkz. `core/tools/isaac_sim_workflow.py`).
3. **Tam paket**  
   `python -m pytest core/tests -q`
4. **E2E / senaryo**  
   Değişiklik kritikse `core/tools/e2e_regression.py` ile uçtan uca doğrulayın.

Semantic navigation ve Isaac görev tamamlama regresyonları için önerilen kısa yol:

1. `python -m core.tools.sim_campaign_launcher --template semantic_navigation_regression --report-out <json>`
2. Rapor içinde `release_gate_summary.release_gate_status` kontrol edin.
3. Çoklu seed karşılaştırması gerekiyorsa `run_multi_seed_sim_learning_campaign` ile
   `summary.release_gate_histogram` ve leaderboard satırlarındaki `release_gate_status`
   alanlarını inceleyin.

CI benzeri güven için, localde en az bir kez tam `core/tests` koşmanız önerilir.

## Ops / canlı telemetri paneli

Gerçek robot veya bench telemetrisi akıyorsa aşağıdaki ops yüzeyleri kullanılabilir:

- `GET /ops/hardware_telemetry`
  Canlı HTML paneli. Joint bazında position / velocity / effort / current / temperature
  tablosu ile IMU, kontak, harness, estop ve fault görünümünü gösterir.
  Ayrıca sıcaklık / akım / effort için mini trend grafikleri, joint alarm eşikleri,
  seçili joint için detay zaman serisi, `30s / 60s / all` pencere filtresi, CSV export
  istemci tarafında PNG grafik export ve üstte sticky hot-joint uyarı bandı içerir.
- `GET /ops/hardware_telemetry/data`
  Panelin beslendiği birleşik JSON snapshot’ı. `hardware.telemetry`,
  `hardware.protocol` ve `robot.diagnostics` sorgularını birleştirir.
  `thresholds`, `trend_history`, `available_joints`, `selected_joint`,
  `selected_window_s`, `joint_detail_history` ve joint bazlı `alarm_state`
  alanlarını da döndürür.
- `GET /ops/hardware_telemetry/joint.csv?joint=<joint_name>`
  Seçili joint için son trend hafızasını CSV olarak indirir.

Alarm durumu `nominal -> warn/critical` geçişine girdiğinde panel verisi bir
`sticky_alert` ve `alert_transition` nesnesi taşır. Bu geçişler artık
`hardware_alert_monitor` tarafından event-driven izlenir; yani
`/ops/hardware_telemetry/data` read-only kalır. Ops audit açıksa geçiş kalıcı
log’a yazılır ve aynı anda tek seferlik `voice.say` uyarısı yayınlanır.
Monitor ayrıca warn/critical clear histerezisi uygular; böylece eşik çevresindeki
küçük salınımlar alarm spam’i üretmez.

Bu panel özellikle şu alanları izlemek için tasarlandı:

- servo konumu ve hızları
- sıcaklık / akım / tork tepeleri
- sıcaklık / akım / tork trendleri ve warn/critical eşikleri
- tek joint için detay position / current / temperature zaman serisi
- IMU ve temas sensörü hazır olma durumu
- estop / harness / degraded mode / fault bilgileri

## Yerel ses testi

Production profil, motion/hardware stack içerdiği için gerçek saha öncesinde
shadow komut günlüğü ister. Sadece mikrofon/HTTP ses hattını denemek için
production yerine güvenli bir yerel profil seçin:

12 dilli yazılım sözleşmesi, provider sınırları ve henüz fiziksel olarak
qualification almamış ASR/TTS yetenekleri için
[`docs/LANGUAGE_SPEECH_ARCHITECTURE.md`](docs/LANGUAGE_SPEECH_ARCHITECTURE.md)
dokümanına bakın.

```bash
pip install -e ".[web,voice]"
CORE_HTTP_VOICE_TOKEN=local-voice-token HUMANOID_RUNTIME_PROFILE=embodied_interactive python -m core.run_app
CORE_HTTP_VOICE_TOKEN=local-voice-token MIC_DEVICE=0 python mic_stt_bridge.py
```

HTTP router komutu terminali meşgul eder; mikrofon bridge'ini ikinci terminalde
çalıştırın. Varsayılan mikrofon bulunamazsa cihazları listeleyip gerçek index
veya isimle seçin; `<...>` placeholder'ını terminale aynen yazmayın:

```bash
python -m sounddevice
MIC_LIST_DEVICES=1 python mic_stt_bridge.py
MIC_DEVICE=0 python mic_stt_bridge.py
MIC_DEVICE=UC02 python mic_stt_bridge.py
```

Yapılandırılmış yerel çok-dilli batch ASR ve neural WAV TTS örneği:

```bash
CORE_ASR_PROVIDER=openai_compatible CORE_ASR_BASE_URL=http://127.0.0.1:8000/v1 \
  CORE_ASR_MODEL=whisper-large-v3 \
  python -m core.tools.speech_transcribe sample.wav --locale tr

CORE_TTS_PROVIDER=openai_compatible CORE_TTS_BASE_URL=http://127.0.0.1:8000/v1 \
  CORE_TTS_MODEL=local-multilingual-tts CORE_TTS_VOICE=default-voice \
  CORE_HTTP_VOICE_TOKEN=local-voice-token \
  HUMANOID_RUNTIME_PROFILE=embodied_interactive python -m core.run_app
```

Bu yapılandırma qualification anlamına gelmez. Stable dil/ses qualification,
12 dilde toplam 6000 hash doğrulamalı gerçek WAV vaka ve insan değerlendirmesi
olmadan PASS vermez; kapı komutu ve kanıt şeması
[`docs/LANGUAGE_SPEECH_ARCHITECTURE.md`](docs/LANGUAGE_SPEECH_ARCHITECTURE.md)
içinde tanımlıdır.

Sadece HTTP router smoke testi için daha küçük profil:

```bash
CORE_HTTP_VOICE_TOKEN=local-voice-token HUMANOID_RUNTIME_PROFILE=minimal python -m core.run_app
curl -s http://127.0.0.1:8777/stt/final \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer local-voice-token' \
  -d '{"text":"mamula merhaba","lang":"tr","confidence":1.0,"confidence_source":"manual_smoke"}'
```

Production shadow bring-up özellikle isteniyorsa:

```bash
MAMULA_HARDWARE_SHADOW_COMMANDS=1 HUMANOID_RUNTIME_PROFILE=production python -m core.run_app
```

## Sesli fiziksel komut risk kapısı

`/stt/final` hattında fiziksel komutlar artık risk seviyesine ayrılır:

- `Level 0`: sohbet / bilgi isteme
- `Level 1`: güvenli sistem komutu (`dur`, `iptal`, `bekle`)
- `Level 2`: düşük riskli hareket
- `Level 3`: locomotion / manipulation
- `Level 4`: yüksek riskli fiziksel niyet

Uygulanan kapılar:

- `Level 1` komutları wake olmadan da güvenli sistem override olarak geçebilir.
- `Level 3` ve `Level 4` komutlarında wake-word zorunludur.
- `Level 3+` için taze telemetri, safety-ready durum ve operator policy kontrolü zorunludur.
- Policy auto-approve etmiyorsa komut kullanıcı onayına düşer.
- Dispatch edilen `voice.task` olaylarının `meta.extra` alanına risk seviyesi, approval gereksinimi ve approval durumu yazılır.
- Aynı risk bilgisi planner/action zincirinde ikinci kez doğrulanır; `wake`/`approval` meta'sı eksikse veya canlı telemetri-safety kapısı son anda bozulmuşsa `executive.action` öncesinde bloklanır.

## Veri ve güvenlik notları

- Varsayılan donanım çıktıları: `data/hardware/` (komut günlüğü, telemetri, kalibrasyon; çalışma dizinine göre değişir).
- Isaac köprü durumu: `data/isaac_session_bridge/` veya araçta verilen `--bridge-root` ile aynı olmalıdır.

## C++ low-level migration (başlangıç)

Low-level control katmanını C++'a taşımak için başlangıç iskeleti eklendi:

- Konum: `native/control_core/`
- Plan dokümanı: `core/docs/cpp_low_level_migration_v1.md`

Phase-1 build:

```bash
cmake -S native/control_core -B native/control_core/build
cmake --build native/control_core/build --config Release
```

Bu fazda hedef, kontrol çekirdeği API/entegrasyon yüzeyini sabitlemek; business logic büyük ölçüde
hala Python modüllerinde kalır.

Phase-2 bridge modülü:

- `core/modules/robot/cpp_control_bridge_module.py`
- Shadow geçiş modu (phase-3 hazırlık; kontrol çekirdeği native parity): üst seviye motor/driver shadow’u (`MAMULA_HARDWARE_SHADOW_COMMANDS`) ile karıştırmayın — prosedür: [`core/docs/real_robot_shadow_transition_v1.md`](core/docs/real_robot_shadow_transition_v1.md).
  - `CONTROL_CORE_CPP_SHADOW_CORE=1`
  - `CONTROL_CORE_CPP_PRIMARY_OUTPUT=1` (candidate çıktıyı ana topic'e promote eder)
  - modül bazlı override:
    - `CONTROL_CORE_CPP_PRIMARY_COMPILER=1`
    - `CONTROL_CORE_CPP_PRIMARY_ESTIMATOR=1`
    - `CONTROL_CORE_CPP_PRIMARY_SCHEDULER=1`
    - `CONTROL_CORE_CPP_PRIMARY_TASK_PRIORITY=1`
    - `CONTROL_CORE_CPP_PRIMARY_QP_CONTROLLER=1`
    - `CONTROL_CORE_CPP_PRIMARY_QP_SOLVER=1`
    - `CONTROL_CORE_CPP_PRIMARY_IK_SOLVER=1`
    - `CONTROL_CORE_CPP_PRIMARY_ID_SOLVER=1`
  - profile preset (env yoksa otomatik):
    - `s422_light`: scheduler primary
    - `s422`: scheduler + compiler primary
  - aktif olduğunda aşağıdaki modüller davranışı koruyarak C++ bridge'e mirror eder:
    - `deterministic_control_scheduler`
    - `state_estimator`
    - `actuator_command_compiler`
    - `task_priority_resolver`
    - `whole_body_qp_controller`
    - `real_qp_solver`
    - `whole_body_inverse_kinematics`
    - `whole_body_inverse_dynamics`
- Backend seçimi:
  - `CONTROL_CORE_BACKEND=python|cpp`
  - `CONTROL_CORE_BRIDGE_BIN=<native bridge path>`
- Topic'ler:
  - `hardware.actuator_command_bundle` (route girişi)
  - `control.core.command`
  - `control.core.reply`
  - `control.core.latency`
  - `control.core.latency.metrics` (aggregate p50/p95/p99)
  - `control.core.latency.query` / `control.core.latency.result`
  - `control.core.latency.ab.report` (python vs cpp delta / improvement / gate)
  - `control.core.latency.ab.query` / `control.core.latency.ab.result`
  - `control.core.query` / `control.core.result`
  - `control.core.rollout.query` / `control.core.rollout.result`
  - `control.core.phase3.readiness.query` / `control.core.phase3.readiness.result` (candidate/primary coverage)
  - `control.core.phase3.decision` (go/no-go + reasons) (drift alan?: `rollout_drift.has_drift`, `rollout_drift.severity`, `rollout_drift.warnings`)

A/B gate threshold env değişkenleri:

- `CONTROL_CORE_AB_AVG_MAX_DELTA_MS` (varsayılan: `0.0`)
- `CONTROL_CORE_AB_P95_MAX_DELTA_MS` (varsayılan: `0.0`)
- `CONTROL_CORE_AB_P99_MAX_DELTA_MS` (varsayılan: `0.0`)

Profile preset desteği:

- Profil çözümleme sırası: `CONTROL_CORE_AB_PROFILE` -> `HUMANOID_RUNTIME_PROFILE` -> `CORE_RUNTIME_PROFILE` -> `default`
- Dahili presetler:
  - `s422_light`: `avg=0.0`, `p95=0.0`, `p99=0.0` (sıkı)
  - `s422`: `avg=1.0`, `p95=2.0`, `p99=3.0` (daha toleranslı)
- Not: Açık env threshold değerleri presetlerin üzerine yazılır.

## Reasoning Self-Protection (AI Safety Gate)

`ReasoningModule`, düşük güvenli ve riskli aksiyonlarda (özellikle hareket/manipülasyon)
otomatik olarak güvenli moda düşebilir.

Profil bazlı varsayılan eşikler:

| Profil | Varsayılan `self_protection_min_confidence` |
|---|---|
| `production` | `0.45` |
| `s40` / `embodied_reasoned` | `0.65` |
| `identity_perception_hardware` | `0.80` |

Env override (profil varsayılanlarının üstüne yazar):

- `REASONING_SELF_PROTECTION_MIN_CONFIDENCE` (`0.0 - 1.0`)

Örnek:

```bash
REASONING_SELF_PROTECTION_MIN_CONFIDENCE=0.90 CORE_RUNTIME_PROFILE=production python -m core.run_app
```

Notlar:

- Değer parse edilemezse modül, profile bağlı default değere geri döner.
- Gate tetiklenirse `reasoning.self_protection` olayı yayınlanır ve plan güvenli konuşma fallback’ine döner.

## Kimler için?

- Robotik ve yazılım ekipleri: MAMULA’nın davranışını genişletmek, yeni profiller ve modüller eklemek.
- Araştırma ve entegrasyon: Isaac, sesli arayüz ve gövde API’si ile deney yapmak isteyen geliştiriciler.

## Geliştiriciler için hızlı başlangıç

```bash
pip install -e ".[dev]"
python -m pytest
```

Phase3 + native bridge smoke doğrulaması (standart tek komut):

```bash
python core/scripts/run_phase3_validation.py
```

Native build + validation (cmake varsa):

```bash
python core/scripts/run_phase3_validation.py --build-native
```

Metrics exporter testlerini dahil ederek doğrulama:

```bash
python core/scripts/run_phase3_validation.py --check-metrics-exporter
```

Validation sonrası evidence bundle toplama (opsiyonel draft update ile):

```bash
python core/scripts/run_phase3_validation.py --check-metrics-exporter --collect-evidence --evidence-out-dir logs/phase3_evidence --update-evidence-drafts
```

Validation + evidence sonrası closure readiness gate (opsiyonel):

```bash
python core/scripts/run_phase3_validation.py --check-metrics-exporter --collect-evidence --evidence-out-dir logs/phase3_evidence --update-evidence-drafts --check-closure-readiness
```

Aynı akışta hardware evidence dahil etmek için:

```bash
python core/scripts/run_phase3_validation.py --check-metrics-exporter --collect-evidence --evidence-out-dir logs/phase3_evidence --update-evidence-drafts --with-hardware-evidence --hardware-root-dir data/hardware --check-closure-readiness
```

Release-gate strict mod (native smoke skip olmaz, binary zorunlu):

```bash
python core/scripts/run_phase3_validation.py --strict
```

Strict mod davranışı:

- Native bridge binary (`native/control_core/build/control_core_bridge(.exe)`) yoksa script pytest'e geçmeden `exit 2` ile fail eder.
- Binary yolu override etmek için `CONTROL_CORE_BRIDGE_BIN` kullanılabilir.
- Mesaj olarak düzeltme adımı verir: `--build-native` çalıştır veya `CONTROL_CORE_BRIDGE_BIN` set et.

CI için önerilen gate komutu (build + strict):

```bash
python core/scripts/run_phase3_validation.py --build-native --strict --check-metrics-exporter
```

Repo içi GitHub Actions gate:

- `.github/workflows/phase3-strict-gate.yml`
- push (`main`/`master`), pull request ve manuel tetikleme (`workflow_dispatch`) olaylarında çalışır.
- Önce `phase3-metrics-fast` job'ı ile exporter testlerini (`test_export_phase3_metrics.py`, `test_run_phase3_metrics_stack.py`) hızlıca koşar.
- `phase3-metrics-fast` sonunda smoke event dosyası + `/metrics` çıktısı artifact olarak yüklenir (`phase3-metrics-fast-evidence`).
- Ardından `phase3-strict` job'ı (`needs: phase3-metrics-fast`) strict gate komutunu (`--check-metrics-exporter`, `--collect-evidence`, `--update-evidence-drafts` dahil) çalıştırır.
- Strict job sonunda `logs/phase3_evidence_ci` klasörü artifact olarak yüklenir (`phase3-evidence-<os>`).
- Ek olarak `phase3-closure-readiness-report` job'ı non-blocking (`continue-on-error`) şekilde closure readiness raporu üretir ve artifact olarak yükler (`phase3-closure-readiness-report`).
- CI evidence akışında hardware kanıtı da toplanır (`--with-hardware-evidence --hardware-root-dir data/hardware`).
- Closure readiness job summary'sinde manifest özeti de yayınlanır (`file_count`, `checks_count`, `closure_overall_ready`, required evidence files).
- Gate, `ubuntu-latest` ve `windows-latest` üzerinde paralel koşar.
- Aynı branch için önceki koşuları otomatik iptal eder (`concurrency`) ve her job için 30 dk timeout uygular.

CI örneği (binary yolu explicit):

```bash
CONTROL_CORE_BRIDGE_BIN=/workspace/native/control_core/build/control_core_bridge \
python core/scripts/run_phase3_validation.py --strict
```

Not: `--build-native --strict` birlikte kullanıldığında `cmake` yoksa build skip edilmez; strict gereği fail edilir.

Python yolu proje kökünü içermelidir (`pytest.ini` içinde `pythonpath = .` tanımlıdır).

Orchestrator eval gate (test tiers) notları:

- `.github/workflows/test-tiers.yml` içinde iki ayrı gate çalışır:
  - Genel kalite gate: `core.tools.run_orchestrator_eval_gate`
  - Domain gate (kademeli rollout): `core.tools.run_orchestrator_eval_gate --require-domains ...`
- Workflow içindeki merkezi varsayılanlar (job-level `env`):
  - `ORCH_EVAL_MIN_DAYS=3`
  - `ORCH_EVAL_MIN_QUALITY=65`
  - `ORCH_EVAL_MAX_NEGATIVE_DELTA=-8`
  - `ORCH_EVAL_REQUIRED_DOMAINS_DEFAULT=physics,chemistry` (kademeli rollout fazı 1; tam set için org/repo variable kullanın)
  - `ORCH_EVAL_DOMAIN_THRESHOLDS_JSON_DEFAULT=<tek satır JSON>` (physics/chemistry için sıkı; biology/history/coğrafya için daha gevşek hazır eşikler; faz 2’de domain listesini genişletince aynı JSON kullanılmaya devam eder)
- Org/repo `ORCH_EVAL_REQUIRED_DOMAINS` yoksa job varsayılan CSV (faz 1: `physics,chemistry`) kullanılır. Domain gate’i tamamen kapatmak için org/repo variable: `ORCH_EVAL_SKIP_DOMAIN_GATE=1`.
- Faz 2 genişletme örneği:
  - `ORCH_EVAL_REQUIRED_DOMAINS=physics,chemistry,biology,history,geography`
- Domain başına eşik override (repo/org variable ile tamamen değiştirilebilir; boş bırakılırsa job’daki `ORCH_EVAL_DOMAIN_THRESHOLDS_JSON_DEFAULT` kullanılır):
  - `ORCH_EVAL_DOMAIN_THRESHOLDS_JSON={"physics":{"min_quality":72,"max_negative_delta":-6,"min_days":3},"chemistry":{"min_quality":72,"max_negative_delta":-6,"min_days":3},"biology":{"min_quality":70,"max_negative_delta":-7,"min_days":3},"history":{"min_quality":68,"max_negative_delta":-8,"min_days":3},"geography":{"min_quality":68,"max_negative_delta":-8,"min_days":3}}`
- PR strict davranışı:
  - Genel gate: `ORCH_EVAL_GATE_STRICT_ON_PR=1`
  - Domain gate: `ORCH_EVAL_DOMAIN_STRICT_ON_PR=1`
- Main/master branch'te her iki gate de blocking çalışır.
- CI log’unda tek satır özet: `core.tools.ci_print_orchestrator_eval_summary` (genel gate) ve `core.tools.ci_print_domain_gate_summary` (domain gate) workflow’da gate koşulundan hemen sonra çalışır; artifact indirmeden `ok/reason/last_quality/failed_domains` görünür.
- Domain eşleştirmesi varsayılan olarak `domain` alanından yapılır; farklı alan adı gerekirse
  `--domain-field <field_name>` (veya `CORE_ORCH_EVAL_GATE_DOMAIN_FIELD`) kullanılabilir.

## İsim ve kapsam

**MAMULA** bu projede insansı robot platformunun ürün adı olarak kullanılır. Bu depo, o platformun **çekirdek** yazılımını içerir; donanım CAD’i veya tüm üretim dağıtımı burada yer almayabilir.


- `control.core.rollout.result` i?inde solver policy g?r?n?r (`qp_solver`, `ik_solver`, `id_solver`).
- Ayn? rollout sonucunda autopilot i?in `autopilot_policy.preset`, `autopilot_policy.effective`, `autopilot_policy.sources` alanlar? da vard?r.
- Ayn? rollout sonucunda `phase3_observability.decision` snapshot'? her zaman standart alanlarla gelir:
  - `decision`, `confidence`, `recommended_next_action`
  - `severity`, `reason_code`, `runbook_hint`
  - `failed_gates`, `ts_ms`
- Kaynak önceliği: `control.core.phase3.decision` alanları -> `control.core.phase3.readiness.result.decision_preview` fallback -> güvenli default.

Runtime contract checklist (phase3/rollout/autopilot):

| Topic | Zorunlu alanlar (minimum) | Operasyon amacı |
|---|---|---|
| `control.core.phase3.readiness.result` | `summary`, `gates`, `bridge.core_diagnostics`, `threshold_policy`, `decision_preview` | Gate ve coverage görünürlüğü + decision fallback kaynağı |
| `control.core.phase3.decision` | `decision`, `confidence`, `recommended_next_action`, `severity`, `reason_code`, `runbook_hint`, `failed_gates`, `policy_trace`, `ts_ms` | Go/no-go kararı ve anlık aksiyon yönü |
| `control.core.rollout.result` | `phase3_observability`, `phase3_policy_snapshot`, `health_summary`, `rollout_drift`, `autopilot_policy`, `ts_ms` | Tek payload'ta operasyonel durum özeti |
| `control.core.phase3.autopilot.result` | `enabled`, `allowlist`, `max_solver_risk_score`, `solver_risk_score`, `last_action`, `policy_snapshot`, `ts_ms` | Autopilot runtime policy + son aksiyon görünürlüğü |
| `control.core.phase3.autopilot.action` | `action`, `severity`, `reason_code`, `runbook_hint`, `ts_ms` | Dashboard/alert için event-level alarm sinyali |

Önerilen SLO/alert kuralları (başlangıç):

| Kural | Koşul (rolling window) | Önerilen seviye | Operatör aksiyonu |
|---|---|---|---|
| Solver risk hard-stop | `skip_solver_risk_guard` >= 1 / 5 dk | `critical` | Promote dondur; QP/IK/ID residual ve limit violation trendini düşür |
| Stabilizasyon bekleme | `skip_solver_stabilization` >= 3 / 10 dk | `warn` | `stabilize_solver_convergence` runbook adımlarını uygula, sonra tekrar dene |
| Risk verisi kaybı | `skip_missing_risk_data` >= 3 / 10 dk | `warn` (20 dk sürerse `critical`) | Telemetri hattını (family_trends + solver_risk_score) geri getir |
| Readiness gate fail | `phase3.decision.decision=no-go` >= 3 ardışık poll | `warn` | `failed_gates` ve `policy_trace` üzerinden kök neden ayrıştır |
| Bridge kalite bozulması | `health_summary.diagnostics_reject_rate > 0.2` >= 2 / 5 dk | `critical` | Bridge/core hata sınıflarını incele, rollout'u güvenli profile çek |
| Rollout drift | `rollout_drift.has_drift=true` >= 10 dk | `warn` | Env/preset çakışmalarını temizle, tek policy kaynağına dön |

Prometheus/Grafana alert rule iskeleti (öneri):

- Örnek metric isimleri (topic payload'larından türetilmiş):
  - `control_core_autopilot_action_total{action,severity,reason_code}`
  - `control_core_phase3_decision_total{decision,severity,reason_code}`
  - `control_core_rollout_drift{profile}` (0/1 gauge)
  - `control_core_diagnostics_reject_rate` (gauge)
  - `control_core_solver_risk_score` (gauge)

```yaml
groups:
  - name: control-core-phase3
    rules:
      - alert: ControlCoreSolverRiskHardStop
        expr: increase(control_core_autopilot_action_total{action="skip_solver_risk_guard"}[5m]) >= 1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Solver risk guard triggered"
          description: "Autopilot promotion blocked by solver risk threshold."

      - alert: ControlCoreRiskDataMissing
        expr: increase(control_core_autopilot_action_total{action="skip_missing_risk_data"}[10m]) >= 3
        for: 2m
        labels:
          severity: warn
        annotations:
          summary: "Risk telemetry missing"
          description: "family_trends and/or solver_risk_score pipeline degraded."

      - alert: ControlCoreReadinessNoGoStreak
        expr: increase(control_core_phase3_decision_total{decision="no-go"}[10m]) >= 3
        for: 1m
        labels:
          severity: warn
        annotations:
          summary: "Repeated no-go decisions"
          description: "Inspect failed_gates and policy_trace for root cause."

      - alert: ControlCoreBridgeRejectRateHigh
        expr: max_over_time(control_core_diagnostics_reject_rate[5m]) > 0.2
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Bridge reject rate high"
          description: "Control-core bridge/core quality degraded."
```

- Readiness sonucu: `summary.candidate_coverage`, `summary.primary_coverage`, `summary.missing_candidate_stages`, `gates.candidate_ready`, `gates.primary_ready`.
- Readiness solver-risk gate: `gates.solver_risk_gate`, `gates.max_solver_risk_for_go` (go/no-go kararına doğrudan etki eder).
- Readiness threshold kayna??: `threshold_policy.profile`, `threshold_policy.preset`, `threshold_policy.sources` (env/profile_preset).

- Decision alan?: `confidence` ve `recommended_next_action` i?erir.
- Decision i?inde `policy_trace` bulunur; gate baz? pass/fail ve beklenen-ger?ek de?erleri raporlar.
- Decision i?inde `failed_gates` dizisi de vard?r; sadece fail olan gate adlar?n? listeler.
- `high_solver_risk` durumunda `recommended_next_action=stabilize_solver_convergence` döner.

- Opsiyonel autopilot: `CONTROL_CORE_PHASE3_AUTOPILOT=1`
  - girdi: `control.core.phase3.decision`
  - ??kt?: `control.core.rollout.apply.request`, `control.core.phase3.autopilot.action`
  - sorgu: `control.core.phase3.autopilot.query` / `control.core.phase3.autopilot.result`
  - action code notları: `skip_solver_risk_guard`, `skip_missing_risk_data`, `skip_solver_stabilization`, `skip_noop`

- Autopilot allowlist: `CONTROL_CORE_PHASE3_AUTOPILOT_ALLOWLIST=*|qp_solver,qp_controller,...`
- Autopilot tuning env: `CONTROL_CORE_PHASE3_AUTOPILOT_MIN_CONFIDENCE`, `CONTROL_CORE_PHASE3_AUTOPILOT_COOLDOWN_MS`
- Autopilot solver-risk env: `CONTROL_CORE_PHASE3_AUTOPILOT_MAX_SOLVER_RISK_SCORE` (profile preset varsayılanı, env ile override)
- Autopilot defaults profile preset'ten gelir (`CONTROL_CORE_CPP_PROFILE`), env varsa override eder.
- Rollout health özeti solver risk sinyali içerir: `health_summary.solver_risk_score`, `health_summary.solver_risk_level`, `health_summary.solver_risk_reasons`.

Autopilot aksiyon state machine (özet):

| Girdi koşulu | Üretilen aksiyon |
|---|---|
| `recommended_next_action=stabilize_solver_convergence` | `skip_solver_stabilization` |
| `solver_risk_score > max_solver_risk_score` | `skip_solver_risk_guard` |
| `CONTROL_CORE_PHASE3_AUTOPILOT_REQUIRE_RISK_DATA=1` ve risk verisi eksik | `skip_missing_risk_data` |
| `recommended_next_action=maintain_primary_stability` (veya promote adımı yok) | `skip_noop` |
| Confidence/allowlist/cooldown geçerli + promote adımı belirlenmiş | `apply` ( `control.core.rollout.apply.request` yayınlanır ) |

Autopilot action -> alert mapping (öneri):

| Action (`last_action.action`) | Önerilen alarm seviyesi | Operasyon notu |
|---|---|---|
| `apply` | `info` | Beklenen rollout ilerlemesi. |
| `skip_noop` | `info` | O tur için promotable adım yok, izlemeye devam. |
| `skip_missing_risk_data` | `warn` | Risk telemetrisi eksik; veri hattı kontrol edilmeli. |
| `skip_solver_stabilization` | `warn` | Solver stabilizasyonu tamamlanmadan promote yapılmaz. |
| `skip_solver_risk_guard` | `critical` | Yüksek solver riski nedeniyle promote kilitlendi; önce solver tuning gerekir. |

Önerilen alarm payload sözleşmesi (dashboard/alert):

```json
{
  "action": "skip_solver_risk_guard",
  "severity": "critical",
  "reason_code": "solver_risk_threshold_exceeded",
  "runbook_hint": "Tune QP/IK/ID convergence; retry promotion after risk drops.",
  "source_topic": "control.core.phase3.autopilot.result",
  "ts_ms": 1760000000123
}
```

Reason code öneri listesi:

- `apply` -> `rollout_apply_sent`
- `skip_noop` -> `no_promotable_action`
- `skip_missing_risk_data` -> `risk_data_missing`
- `skip_solver_stabilization` -> `solver_stabilization_required`
- `skip_solver_risk_guard` -> `solver_risk_threshold_exceeded`

Kısa operasyon runbook (solver risk):

- `low`: rollout korunur; önerilen aksiyon `maintain_primary_stability` veya bir sonraki modül promote.
- `medium`: yeni promote adımı yavaşlatılır; önce `top_risk_families` ve solver residual/limit violation alanları izlenir.
- `high`: autopilot promote aksiyonu durdurulur (`skip_solver_risk_guard` beklenir); öneri `stabilize_solver_convergence` ise autopilot `skip_solver_stabilization` aksiyonunu yayınlar.

- Phase3 gate env: `CONTROL_CORE_PHASE3_MIN_CANDIDATE_COVERAGE`, `CONTROL_CORE_PHASE3_MIN_PRIMARY_COVERAGE`, `CONTROL_CORE_PHASE3_MAX_ERROR_RATE`.
- Phase3 solver-risk gate env: `CONTROL_CORE_PHASE3_MAX_SOLVER_RISK` (profile preset varsayılanı, env override).
- C++ bridge request contract'ı command bazlı payload key doğrular; uyumsuz istekler `invalid_payload_shape` ve `required_key` ile döner.
