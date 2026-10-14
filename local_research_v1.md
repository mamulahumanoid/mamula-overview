# MAMULA Research v1

MAMULA Research v1, Local RAG v1 üzerinde çalışan tamamen yerel,
kaynak-gösterimli araştırma katmanıdır. Ağa bağlanmaz ve eksik kanıtı
model bilgisiyle tamamlamış gibi göstermez.

## Kanıtlanan davranış

- Ana soru ile operatörün verdiği odak sorgularını ayrı ayrı tarar.
- Aynı dokümandan gelen tekrarları birleştirir ve farklı kaynak sayısını
  zorunlu bir kabul kapısı olarak kullanır.
- Her kanıtı `RES1`, `RES2`, ... kaynağına ve içerik SHA-256 değerine
  bağlar.
- Karşıt kutuplu veya aynı konuya ait farklı sayısal iddiaları olası çelişki
  olarak raporlar; taraflardan birini sessizce seçmez.
- Kaynak çeşitliliği yetersizse `abstained`, maddi çelişki varsa
  `needs_resolution`, yeterli kanıt varsa `evidence_ready` döner.
- Genel sohbet araştırması yalnız `public,household` kapsamını kullanır;
  `owner` kapsamı ayrı yetkilendirme olmadan bağlanmaz.

Bu katman kendi başına serbest biçimli nihai yanıt üretmez. Önce denetlenebilir
bir evidence pack üretir. Yerel dil modeliyle sentez gerekiyorsa
`format_research_synthesis_prompt()` kanıtı güvenilmeyen veri olarak sarar,
belge içindeki talimatların ve araç çağrılarının uygulanmasını yasaklar.

## Kullanım

```bash
python -m core.tools.local_research \
  "Stable release için hangi kanıtlar gerekiyor?" \
  --db runtime/db/local_rag_v1.db \
  --scope public \
  --minimum-sources 3 \
  --focus "security evidence SBOM signatures provenance" \
  --focus "deployment healthz readyz metrics shadow smoke" \
  --out runtime/research/stable-release.json
```

Evidence pack içerik taşıdığı için `--out` dosyası `0600` izinle yazılır.
Komut yalnız `evidence_ready` sonucunda sıfır exit code döner; çelişki ve
çekimserlik otomasyonda fail-closed sonuçtur.

## Qualification

Sentetik donmuş sözleşme kapısı:

```bash
python -m core.tools.local_research_eval \
  --out runtime/evidence/local_research_v1_eval.report.json
```

Gerçek yönetilen teknik corpus kapısı:

```bash
python -m core.tools.local_research_corpus_eval \
  --db runtime/db/local_rag_v1.db \
  --cases core/config/local_research_technical_eval.v1.json \
  --out runtime/evidence/local_research_technical_eval.report.json
```

Gerçek-corpus raporu soru ve belge metni yazmaz. Yalnız vaka kimliği, aggregate
metrikler, kaynak sayısı, citation/coverage durumu, corpus fingerprint ve config
SHA-256 değerlerini tutar.

## Üretim aktivasyonu

Research varsayılan olarak kapalıdır. Gerçek-corpus raporu indeksle aynı kalıcı
volume'a kopyalandıktan sonra `CORE_LOCAL_RESEARCH_ENABLED=1` verilebilir.
Research etkinse Local RAG da etkin, local-only ve qualified olmak zorundadır.
`/readyz` ayrıca Research raporunun PASS olduğunu ve rapordaki corpus
fingerprint'in canlı indeksle aynı olduğunu kontrol eder. Eksik veya eski rapor
HTTP 503 üretir. Docker ve systemd değişkenleri
`deploy/systemd/local-research.env.example` içinde gösterilir.

## Bilinen sınır

V1 çelişki analizi deterministic dilsel ve sayısal bir taramadır; mantıksal
doğruluk hakemi değildir. `needs_resolution` insan veya daha güçlü yerel
doğrulama gerektirir. Kaynak güven seviyesi ve zamansal güncellik metadata'sı
V2 kapsamıdır.
