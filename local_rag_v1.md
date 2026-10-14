# MAMULA Local RAG v1

Local RAG v1, ev robotunun izin verilmiş yerel belgelerden internet bağlantısı
olmadan kaynak gösterimli bağlam üretmesini sağlar. Bu katman model eğitimi
değildir; doküman değiştiğinde yeniden eğitim yerine ilgili indeks kaydı
güncellenir.

## Güvenlik ve gizlilik sınırları

- Kaynak dosya, ingest sırasında verilen `--root` altında olmalıdır.
- Sembolik bağlantılar ve kök dışına kaçan yollar reddedilir.
- İndeks varsayılan olarak private runtime dizinindeki
  `db/local_rag_v1.db` dosyasındadır ve dosya modu `0600` yapılır.
- Her doküman `public`, `household`, `owner` gibi açık bir erişim kapsamıyla
  indekslenir. Sorguda izin verilen kapsam yoksa retrieval fail-closed sonuçlanır.
- Kullanıcıya dönen citation yalnız göreli kaynak adı, chunk konumu ve içerik
  SHA-256 değeri taşır; mutlak yerel yol taşımaz.
- Yeterli kanıt bulunamazsa sonuç `abstained=true` olur. RAG yokluğu modelin
  belgeye dayanmayan bir yanıtı kaynaklıymış gibi sunmasına izin vermez.
- Qwen3 embedding modeli çalışma zamanında yalnız yerel dizinden yüklenir.
  İndirme ancak provisioning sırasında açık `--allow-model-download` seçimiyle
  yapılabilir.

## Kurulum

SQLite FTS5 tabanlı lexical retrieval minimal kurulumla çalışır:

```bash
pip install -e ".[dev]"
```

PDF ve Qwen3 embedding tabanlı dense retrieval için:

```bash
pip install -e ".[dev,rag]"
```

Bu extra GPU zorunlu kılmaz. Küçük/orta belge koleksiyonunda lexical sürüm CPU
üzerinde yeterlidir. Dense indeks oluşturmak için yerel bir Qwen3 embedding model
dizini verilmelidir; üretim robotunda model önceden indirilmiş ve doğrulanmış
olmalıdır.

## İndeks yönetimi

Önce özel yerel kaynak dizinlerini oluşturun:

```bash
python -m core.tools.local_rag init-knowledge
```

Bu komut `runtime/knowledge/{public,household,owner}` dizinlerini `0700`, yerel
`corpora.local.json` manifestini `0600` izinle oluşturur. `household` ve `owner`
kökleri grup/dünya erişimine açıksa manifest senkronizasyonu fail-closed durur.
Gerçek belge metinleri repoya veya qualification raporuna yazılmaz.

Bir dokümanı yalnız izin verilen kökün göreli adıyla indeksleyin:

```bash
python -m core.tools.local_rag \
  --db runtime/db/local_rag_v1.db \
  ingest knowledge/robot_handbook.md \
  --root knowledge \
  --scope household
```

Qwen3 embedding ile aynı işlem:

```bash
python -m core.tools.local_rag \
  --db runtime/db/local_rag_v1.db \
  --embedding-model models/Qwen3-Embedding-0.6B \
  --embedding-device cuda \
  ingest knowledge/robot_handbook.md \
  --root knowledge \
  --scope household
```

Sorgu, istatistik ve silme:

```bash
python -m core.tools.local_rag --db runtime/db/local_rag_v1.db \
  query "Robotun servo sayısı kaç?" --scope household
python -m core.tools.local_rag --db runtime/db/local_rag_v1.db stats
python -m core.tools.local_rag --db runtime/db/local_rag_v1.db \
  delete knowledge/robot_handbook.md
```

Bir belge ağacını artımlı senkronize etmek için:

```bash
python -m core.tools.local_rag --db runtime/db/local_rag_v1.db \
  sync knowledge --scope household --prune
```

`--prune` verilmezse kaynağı silinmiş eski indeks kayıtları korunur. Bu seçenek
verildiğinde bile boş bir corpus kökünden toplu silme reddedilir. Gizli dosyalar,
sembolik bağlantılar ve desteklenmeyen uzantılar senkronizasyona alınmaz.

Birden fazla kökü sürüm kontrollü manifestle yönetmek için:

```bash
python -m core.tools.local_rag --db runtime/db/local_rag_v1.db \
  sync-manifest core/config/local_rag_corpora.v1.json
```

Manifest kökleri yalnız manifestteki göreli `base_root` altında kalabilir. Depodaki
varsayılan manifest `core/docs` teknik corpusunu ve `docs` ürün/release corpusunu
`public` kapsamında yönetir.

İçerik SHA-256 değişmediyse tekrar ingest no-op olur. Değiştiyse eski chunk ve
embedding kayıtları tek transaction içinde değiştirilir.

## Sohbet grounding entegrasyonu

Yerel RAG varsayılan olarak kapalıdır. Açıldığında yerel indeks önce sorgulanır;
`CORE_LOCAL_RAG_ONLY=1` varsayılanı internet tabanlı fallback'i engeller:

```bash
export CORE_LOCAL_RAG_ENABLED=1
export CORE_LOCAL_RAG_ONLY=1
export CORE_LOCAL_RAG_DB_PATH=/var/lib/mamula/db/local_rag_v1.db
export CORE_LOCAL_RAG_ALLOWED_SCOPES=public,household
export CORE_LOCAL_RAG_TOP_K=4
export CORE_LOCAL_RAG_MIN_SCORE=0.22
```

Dense retrieval için aynı yerel model sorgu tarafında da tanımlanmalıdır:

```bash
export CORE_LOCAL_RAG_EMBEDDING_MODEL_PATH=/var/lib/mamula/models/Qwen3-Embedding-0.6B
export CORE_LOCAL_RAG_EMBEDDING_DEVICE=cuda
```

Grounding metni `[RAG1]`, `[RAG2]` etiketleriyle gelir. Sohbet prompt'u bu
etiketleri yanıtta korumayı ister. Retrieved belge JSON içinde güvenilmeyen kanıt
olarak sarılır; belge içindeki rol değiştirme, sistem talimatı ve araç çağrısı
isteklerinin uygulanmaması açıkça belirtilir. İndeks yoksa, kapsam geçersizse
veya retrieval hata verirse entegrasyon istisnayı dışarı sızdırmadan abstain eder.

## Qualification

Donmuş kapı; doğru dokümana retrieval@1, citation bütünlüğü, konu dışı soruda
abstention ve owner/household kapsam ayrımını ağsız olarak ölçer:

```bash
python -m core.tools.local_rag_eval \
  --fixture core/config/local_rag_eval_v1.json \
  --out runtime/evidence/local_rag_v1_eval.report.json
```

V1 kabulü için dört metriğin de `1.0` olması gerekir. Bu sentetik sözleşme kapısı,
gerçek ev dokümanlarıyla yapılacak gizlilik onaylı shadow değerlendirmesinin
yerine geçmez.

Gerçek yönetilen teknik corpus için ayrı, içerik yazmayan qualification raporu:

```bash
python -m core.tools.local_rag_corpus_eval \
  --db runtime/db/local_rag_v1.db \
  --cases core/config/local_rag_technical_eval.v1.json \
  --out runtime/evidence/local_rag_technical_eval.report.json
```

Bu rapor yalnız aggregate istatistik, corpus/configuration SHA-256 değerleri,
beklenen ve gözlenen göreli kaynak adları ile skorları içerir. Sorgu metni,
retrieval içeriği ve mutlak yerel yollar rapora yazılmaz.

Corpus, kaynak dosya snapshot'ı, private layout, qualification fingerprint ve
runtime bağlamasını birlikte kontrol etmek için:

```bash
python -m core.tools.local_rag --db runtime/db/local_rag_v1.db doctor
python -m core.tools.local_rag --db runtime/db/local_rag_v1.db doctor \
  --require-runtime-binding
```

İkinci komut ayrıca `CORE_LOCAL_RAG_ENABLED=1`, `CORE_LOCAL_RAG_ONLY=1`, doğru
DB yolu ve yalnız `public,household` kapsamlarını zorunlu kılar. `owner` kapsamı
genel sohbet grounding'ine bağlanamaz; ayrı kimlik/yetki doğrulaması gerektirir.

## Üretim aktivasyonu

Docker ve systemd şablonları Local RAG'ı ağsız (`CORE_LOCAL_RAG_ONLY=1`) fakat
varsayılan olarak kapalı getirir. İndeks, private knowledge layout ve güncel
qualification raporu kalıcı runtime volume'una yerleştirildikten sonra systemd
için `deploy/systemd/local-rag.env.example` dosyası `/etc/mamula/local-rag.env`
olarak kurulabilir. Compose için `CORE_LOCAL_RAG_ENABLED=1` ve
`CORE_LOCAL_RAG_REQUIRE_READY=1` birlikte verilmelidir.

Etkinleştirilmiş Local RAG'da `/readyz`, `doctor --require-runtime-binding`
kapılarının runtime-safe alt kümesini tekrar uygular. Build-time `doctor`, kaynak
snapshot'ını da zorunlu doğrular. Taşınmış production artifact'inde kaynak
dosyaların robotta bulunması gerekmez; SQLite corpus fingerprint'i ile güncel
qualification kanıtının eşleşmesi zorunludur. Eksik/değişmiş indeks, eski
qualification kanıtı, ağ fallback'i veya `owner` scope bağlantısı HTTP 503
üretir. Endpoint belge metni ve mutlak dosya yolu yayımlamaz.
