# Thesis Review

Status: DESIGN IN PROGRESS

Bu belge yalnızca tasarım kaydıdır; gerçek şirket analizi, implementation veya aktif schedule içermez.

## Purpose

Thesis Review, mevcut investment thesis'i yeni material evidence ile karşılaştıran asset-level specialist protocol'dür.

Ana soru:

> Bir varlığı alma veya elde tutma nedenimiz hâlâ geçerli mi?

Başlangıç noktası mevcut investment thesis'tir. Şirketi sıfırdan research etmez veya yeniden anlatmaz; yalnız thesis açısından material olan varsayım değişikliklerini inceler.

## Thesis Structure and Inputs

Kesin schema henüz tasarlanmayacaktır. Mevcut thesis konsept olarak şu parçaları içerebilir:

- Core investment rationale
- Expected growth / business drivers
- Competitive advantage / moat assumptions
- Important financial expectations
- Catalysts
- Key risks
- Thesis dependencies
- Invalidation conditions
- Open questions

Önce compact thesis state, previous thesis status ve review date, ilgili varsayımlar, yeni material evidence ve source/research references kullanılmalıdır. Çağıran protocol'ün ilgili bulguları girdi olabilir. Recommendation değerlendirmesi için mevcut valuation, portfolio context ve ilgili technical context de kullanılır.

Thesis Review özellikle bu varsayımlardan hangilerinin güçlendiğini, zayıfladığını veya bozulduğunu belirlemelidir. Mevcut thesis ya da kritik bağlam eksikse boşluk açıkça belirtilir; önceki yatırım gerekçesi sonradan varsayılarak oluşturulmaz.

## Typical Triggers

- Major earnings change
- Guidance deterioration / improvement
- Important competitive development
- Regulatory development
- Management change
- Acquisition / divestiture
- Business-model change
- Material news
- Important KPI trend
- Single Asset Monitoring escalation
- Portfolio Monitoring escalation
- Manual user request

Earnings Review veya News Monitoring'in thesis-relevant material bulguları da trigger olabilir. Her küçük haber Thesis Review tetiklememelidir; gelişmenin mevcut varsayımlar açısından önemi esas alınır. Kesin materiality ve routing kuralları henüz tasarlanmamıştır.

## Change-Focused Review

```text
Previous Thesis
+
New Material Evidence
        ↓
Which assumptions changed?
        ↓
STRONGER / UNCHANGED / WEAKER / INVALIDATED
```

1. Compact thesis state ve önceki review'u başlangıç noktası olarak oku.
2. Yeni material evidence'ı etkilediği mevcut varsayımlarla karşılaştır; neyin değiştiğini ve neden önemli olduğunu belirle.
3. Güçlenen, zayıflayan veya bozulan varsayımları; yeni ve çözülen riskleri ayır. Devam eden riskleri ve açık soruları koru.
4. Değişimin geçici bir sapma mı, thesis'in temelini etkileyen yapısal bir gelişme mi olduğunu mevcut kanıt ölçüsünde değerlendir. Belirsizlik ve çelişkileri görünür tut.
5. Thesis status ve gerekçesini belirle; recommendation'ı ayrı değerlendir ve yalnız gerekli follow-up / yönlendirmeleri kaydet.
6. Machine Record ve kısa Human Brief üret.

Yeni bulgulara uydurmak için eski varsayımlar sessizce yeniden yazılmamalıdır; önceki beklenti ile yeni evidence arasındaki fark anlaşılabilir kalmalıdır. Evidence weighting ve contradiction handling yöntemleri açık tasarım sorularıdır.

## Thesis Status and Price Independence

Mevcut state seti korunur; yeni thesis state eklenmez:

| Thesis status | Konsept anlamı |
|---|---|
| STRONGER | Yeni evidence mevcut yatırım gerekçesini veya kritik varsayımlarını güçlendiriyor. |
| UNCHANGED | İncelenen evidence, mevcut thesis'te material bir değişiklik göstermiyor. |
| WEAKER | Önemli varsayımlar zayıflıyor; ancak yatırım gerekçesinin geçersizleştiği henüz ortaya konmuş değil. |
| INVALIDATED | Temel yatırım gerekçesinin artık geçerli olmadığını destekleyen güçlü evidence bulunuyor. |

Thesis fiyat hareketinden ayrı değerlendirilmelidir. Price action tek başına thesis değişikliği değildir. Aşağıdaki iki kurgusal durum da mümkündür:

```text
Price: -25%
Thesis: UNCHANGED
```

```text
Price: +30%
Thesis: WEAKER
```

Evidence yetersizliği UNCHANGED kanıtı değildir. Güncel status desteklenemiyorsa önceki status yeni doğrulanmış sonuç gibi sunulmamalı; confidence sınırlaması ve required follow-up belirtilmelidir. Eksik / sonuçlandırılamayan değerlendirmenin kesin temsili schema tasarımına bırakılır; REVIEW REQUIRED bir recommendation state'idir, thesis state değildir.

## Thesis Invalidation

INVALIDATED güçlü bir state olmalıdır. Tek bir kötü quarter veya fiyat düşüşü kendi başına yeterli değildir. Olası invalidation riski ile kanıtla desteklenen invalidation ayrılmalıdır.

Invalidation değerlendirmesine konu olabilecek örnekler:

- Core growth driver'ın yapısal olarak bozulması
- Moat'ın kalıcı biçimde zarar görmesi
- Key thesis assumption'ın yanlış olduğunun ortaya konması
- Kabul edilemez governance / fraud sorunu
- Long-term economics'in materially kötüleşmesi
- Original investment case'in artık mevcut olmaması

Bu örnekler otomatik karar kuralları değildir. Hangi kritik varsayımın veya mevcut invalidation koşulunun hangi evidence ile bozulduğu açıklanmalıdır. Tek dönem içinde yapısal bozulmayı gösteren kanıt da ortaya çıkabilir; belirleyici olan dönem sayısı değil kanıtın thesis açısından anlamıdır. Exact invalidation threshold henüz çözülmemiştir.

## Routing

| Bulgular | Olası yönlendirme |
|---|---|
| Valuation assumptions materially değişmiş | Valuation Update |
| Chart / market behavior materially değişmiş | Technical Review |
| Evidence yetersiz | Hedefli follow-up / deeper research consideration |
| Major portfolio implications | Portfolio Monitoring / Full Portfolio Review context |

Her Thesis Review bütün sub-protocol'ları otomatik çalıştırmamalıdır. Deep Research varsayılan adım değildir; mevcut evidence ciddi biçimde yetersizse veya şirket materially değişmişse değerlendirilebilir. Escalation'ın kesin koşulları açık bırakılmıştır.

Portfolio-level etkiler ilgili review için bağlam sağlar; Thesis Review kendi başına portfolio sizing veya execution kararı vermez. Önerilen follow-up, gerçekten tetiklenen protocol ve tamamlanan sonuç birbirinden ayrılmalıdır.

## Recommendation Relationship

Thesis Status ile Recommendation ayrı tutulmalıdır. Mevcut recommendation seti **ADD, HOLD, REDUCE, SELL, REVIEW REQUIRED** olarak korunur. Recommendation; thesis, valuation, portfolio context ve ilgili olduğunda technical context birlikte değerlendirilerek oluşturulur. Tanımlar [System Overview](../architecture/system-overview.md#recommendation-states) ile uyumludur.

Aşağıdakiler yalnızca kurgusal boyut ayrımı örnekleridir:

```text
Thesis: STRONGER
Valuation: EXPENSIVE
Recommendation: HOLD
```

```text
Thesis: WEAKER
Valuation: ATTRACTIVE
Recommendation: REVIEW REQUIRED
```

INVALIDATED thesis çoğu durumda SELL consideration yaratabilir; ancak otomatik SELL command değildir. Yetersiz evidence veya önemli inceleme ihtiyacı REVIEW REQUIRED ile ifade edilebilir. Recommendation execution command değildir; final investment / action authority kullanıcıdadır.

## Outputs

Dual-output principle geçerlidir.

### Machine Record

Kesin schema: DESIGN PENDING. Konsept olarak compact kayıt şu bilgileri taşıyabilir:

- Protocol adı ve instrument
- Review date / timestamp
- Previous thesis status
- New thesis status ve kısa gerekçesi
- Strengthened assumptions
- Weakened assumptions
- Broken assumptions
- New risks
- Resolved risks
- Open questions
- Recommendation ve kısa gerekçesi
- Confidence ve material evidence sınırlamaları
- Required follow-up
- Triggered sub-protocols ve bekleyen sonuçlar
- Source/research references

Alan tipleri, zorunlulukları, database / JSON schema veya saklama yöntemi bu belgede belirlenmez.

### Human Brief

30–60 saniyede okunabilir, sade Türkçe ve değişiklik odaklı olmalıdır. Thesis status, recommendation, en önemli değişiklik, temel risk ve gerekli aksiyon / follow-up öne çıkarılır. Kararı etkileyen evidence boşluğu varsa kısaca belirtilir.

Aşağıdaki yalnızca kurgusal tasarım örneğidir; gerçek ticker analizi veya investment recommendation değildir:

```text
ÖRNEK ŞİRKET — THESIS REVIEW

Thesis: UNCHANGED
Recommendation: HOLD

Ne değişti?
Büyüme mevcut thesis beklentisiyle uyumlu.
Maliyet baskısı sürüyor; mevcut kanıt temel yatırım gerekçesini bozmuyor.

Risk:
Marjların toparlanmasına ilişkin açık soru devam ediyor.

Aksiyon:
Pozisyonu koru. Bir sonraki earnings'te maliyet trendini tekrar kontrol et.
```

## Efficiency and Architecture Relationship

Thesis Review bütün research'i sıfırdan okumamalıdır. Önce compact thesis state kullanılmalı; eski research'e yalnız thesis-critical evidence gerektiğinde inilmelidir. Amaç değişiklik odaklı çalışmak ve tekrar research'i azaltmaktır.

Thesis Review, [Single Asset Monitoring](single-asset-monitoring.md) tarafından çağrılabilen, [Earnings Review](earnings-review.md) tarafından tetiklenebilen ve [Portfolio Monitoring](portfolio-monitoring.md) / News Monitoring escalation sonucu çalışabilen asset-level specialist protocol'dür. Single Asset Monitoring tarafından çağrıldığında bulguları onun asset-level synthesis'ine girdi sağlar. Deep Research'in yerine geçmez.

Thesis representation, assumption structure, invalidation threshold, confidence, evidence weighting, contradiction handling, freshness ve Deep Research escalation konuları [Open Design Questions](../architecture/open-design-questions.md) içinde açık bırakılmıştır.
