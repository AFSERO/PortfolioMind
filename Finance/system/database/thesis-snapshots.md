# Part 5C — Thesis Snapshot + Change Window

## Model ve history

`thesis_snapshots`: UUID id/instrument_id; UTC `as_of` ve `created_at`;
`core_investment_rationale`; JSONB listeleri: `key_assumptions`, `growth_drivers`,
`moat_or_competitive_assumptions`, `key_risks`, `invalidation_conditions`,
`key_kpis`, `catalysts`, `open_questions`, `source_artifact_references`;
nullable kısa `confidence` ve `source_protocol_run_id`.

Repository caller-owned transaction kullanır, commit yapmaz; bağımsız record döner.
Structured alan başına en fazla 20 öğe, toplam içerik için 12.000 UTF-8 byte sınırı
uygular. Bu sınır application creation API'sine aittir; raw SQL için ingestion
validation sistemi kurulmadı. Kaynaklar dosya/bölüm referanslarıdır, rapor içeriği
yüklenmez. Source run instrument eşleşmesi repository ve DB trigger ile korunur.

History append-only: UPDATE/DELETE database trigger tarafından reddedilir.
Instrument/run foreign key'leri RESTRICT kullanır. Düzeltme yeni snapshot'tır.
Snapshot oluşturma current IntelligenceState veya ProtocolRun değiştirmez.

## Latest ve baseline seçimi

Active flag yerine `as_of <= applicable_at` koşuluyla
`as_of DESC, created_at DESC, id DESC LIMIT 1` seçildi. Default applicable_at UTC
şimdidir; gelecekteki snapshot erkenden context'e girmez. Aynı thesis tarihindeki
daha yeni oluşturulan kayıt seçilir; aynı creation timestamp için UUID deterministik
tie-break'tir. Böylece active-flag switch ve eski kayıt güncellemesi gerekmez.

Context Builder `thesis_snapshot` altında yalnız seçilen compact record'u verir;
snapshot yoksa `null`. Diğer instrument snapshot'ları ve eski thesis içerikleri
bu alana taşınmaz. Context Builder dosya okumaz.

Thesis Review evidence başlangıcı sırasıyla `IntelligenceState.last_review_at`,
latest applicable snapshot `as_of`, ikisi yoksa UTC now − 30 gündür. State tarihi
snapshot'tan eski olsa bile istenen öncelik korunur; tarihler ayrı görünür.
Future `last_review_at` sessizce kullanılmaz, hata verir. Naive snapshot tarihleri
reddedilir; aware girdiler UTC'ye çevrilir.

Provider'a `since=start, until=now, limit=news_limit` verilir. Dönüşte instrument,
inclusive yayın zamanı sınırları ve adet sınırı tekrar uygulanır. `news_limit=0`
provider çağırmaz. Baseline için kısa DB okuması workflow provider çağrılarından
önce kapanır. Supplemental context `baseline_review_at`, `thesis_snapshot_as_of`,
`evidence_window_start/end`, `baseline_source` ve materiality rehberini içerir.

Yayın tarihi olayın yeni olduğunu kanıtlamaz. Baseline öncesi olayın tekrar haberi
yeni material change değildir; yeni finansal sonuç, regulatory filing, değişen
deal terms veya yeni thesis-relevant evidence farklı değerlendirilebilir. AI bu
ayrımı yapar. Boş pencere ya da eksik veri tek başına UNCHANGED kanıtı değildir.
Historical run otomatik kabul edilmiş thesis güncellemesi sayılmaz.

## UBER bootstrap

Manuel gözden geçirilmiş extraction: `seeds/uber-thesis-2026-09-14.json`.
Pass 3 report/model ve Pass 1–2 research'ten türetildi. Kaynak dosyalar değiştirilmedi;
bu extraction güncel yatırım tavsiyesi veya yeni research değildir. WATCHLIST/MEDIUM,
conditional moat, FCF normalization, valuation-sensitive varsayımlar, AV/insurance
belirsizlikleri ve koşullu monitoring eşikleri korundu. Önceden bilinen DH/AV/bond
gelişmeleri baseline içeriğinde ayrıca işaretlendi.

Research tarihi gün hassasiyetindedir. `2026-09-14T00:00:00Z` muhafazakâr retrieval
başlangıcı seçildi; raporun o saatte tamamlandığı iddia edilmez. Aynı günün eski
haberlerini final materiality değerlendirmesi ayırmalıdır.

Mevcut application DB environment değişkenleriyle repository kökünden:

```powershell
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m investment_intelligence.bootstrap_uber_thesis --instrument-id 9caa9b56-c9cb-45a4-b976-924c06886b2c
```

Explicit UUID doğru UBER/USD/equity kimliği olarak doğrulanır. Instrument row lock,
eşzamanlı bootstrap tekrarlarını sıraya koyar. Aynı dated payload no-op; aynı tarihte
farklı içerik varsa hata verir. Kaynak dosyaların varlığı kontrol edilir; otomatik
yeniden extraction yapılmaz. Source protocol run NULL'dır; önceki review'a yanlış
research provenance atfedilmez.

## Migration ve doğrulama — 2026-09-15

- Yeni migration `0004`; önceki migration dosyaları değişmedi.
- Yerel MVP DB: `0003 → 0004`; Alembic metadata check temiz.
- Oluşturulan snapshot: `f016b1a8-7aa4-4b7a-bb19-86e3e3906106`.
- Bootstrap ikinci çağrı: no-op, aynı UUID.
- UTF-8 snapshot context: 6.165 byte; tüm UBER context: 10.419 byte.
- Tüm IntelligenceState ve ProtocolRun satırları işlem öncesi/sonrası eşit.
- Korunan run: `0c1e9dfd-39c1-4ce8-a77a-a5d0f2cc3f3d`, COMPLETED history olarak kaldı.
- Tam suite: **214 passed**, gerçek PostgreSQL üzerinde izole test database'leri.
- Test kapsamı: persistence/history/latest/future exclusion, instrument isolation,
  missing snapshot, detached data, UTC/naive rejection, content bounds, immutability,
  source-run matching, üç baseline yolu, provider since/until, eski/future fake news,
  bootstrap tekrar güvenliği, state/run korunması ve migration roundtrip/schema match.

Self-review: compact içerik rapor kopyası değil; tarih belirsizliği açık; old-event
materiality salt yayın filtresine bırakılmadı; snapshot history korunuyor. İlk test
turunda eski migration head/table beklentileri başarısızdı; yeni schema beklentileriyle
düzeltildi ve full suite yeniden geçti. Otomatik state application yapılmadı.
UBER Thesis Review yeniden çalıştırılmadı.
