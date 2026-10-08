# Valuation Update

Status: DESIGN IN PROGRESS

Bu belge yalnızca tasarım kaydıdır; gerçek şirket analizi, implementation veya aktif schedule içermez.

## Purpose

Valuation Update, mevcut valuation modelini başlangıç noktası alarak yalnız gerekli varsayımları güncelleyen asset-level specialist protocol'dür.

Ana soru:

> Yeni finansal veriler, yeni thesis varsayımları veya önemli fiyat hareketleri sonrası mevcut valuation hâlâ geçerli mi?

Amaç şirketi sıfırdan değerlemek değildir. Önceki valuation, yeni material inputs ve güncel market price birlikte değerlendirilir. Full rebuild yalnız gerektiğinde ele alınır.

## Typical Triggers

- Yeni earnings
- Guidance değişimi
- Material thesis change
- Significant price move
- Major margin / growth / cash-flow change
- Acquisition / divestiture
- Share dilution / buyback change
- Capital structure change
- Manual user request
- Single Asset Monitoring escalation

Earnings Review, Thesis Review veya Portfolio Monitoring'in material bulguları da yönlendirme oluşturabilir. Her trigger bütün model varsayımlarının değiştiği anlamına gelmez. Fiyat hareketi tek başına valuation modelini değiştirmeyebilir; aynı intrinsic value varsayımlarında market price materially değişirse valuation status değişebilir.

## Existing Valuation First

Önce compact previous valuation state, model assumptions, methodology, valuation date ve ilgili source/research references okunmalıdır. Yeni material inputs, mevcut thesis state ve reference market price ile karşılaştırılmalıdır. Recommendation için portfolio context ve ilgili technical context de kullanılır.

```text
Previous Valuation
+
New Material Inputs
+
Current Market Price
        ↓
Updated Valuation
```

Tüm financial history her run'da baştan okunmamalıdır. Yalnız değişen inputs ve bunların etkilediği varsayımlar güncellenir; gerekli ayrıntılar için ilgili kaynaklara inilir. Önceki model yoksa, çok stale ise veya artık geçerli değilse bu sınırlama açıkça belirtilir; eski sonuç güncelmiş gibi taşınmaz. Hedefli follow-up veya deeper rebuild ihtiyacı kaydedilir. Full rebuild'in kesin koşulları açık tasarım sorusudur.

## Core Review

### Business Value Changed?

Mevcut modele göre şu varsayımlarda material değişiklik olup olmadığı değerlendirilir:

- Growth assumptions
- Margins
- Cash flow
- Reinvestment needs
- Dilution ve buyback etkisi
- Capital intensity
- Risk
- Terminal assumptions
- Business mix
- Guidance
- Capital structure

Hangi varsayımın neden değiştiği ve valuation üzerindeki etkisi açıklanmalıdır. Değişmeyen varsayımlar gereksiz yere yeniden kurulmaz. Thesis'ten gelen değişiklikler ilgili Thesis Review sonucuyla ilişkilendirilir.

### Market Price Changed?

İşletme değerindeki değişim ile market price değişimi ayrı değerlendirilmelidir. Reference price'ın tarihi, para birimi ve karşılaştırılan valuation'ın aynı temelde olması gözetilir; eski fiyat veya uyumsuz veri güncel karşılaştırma gibi sunulmaz.

Aşağıdaki kurgusal örnekler iki etkinin ayrımını gösterir; yüzdeler otomatik status eşikleri değildir:

```text
Business Value: UNCHANGED
Market Price: -25%
Valuation: EXPENSIVE → ATTRACTIVE
```

```text
Business Value: LOWER
Market Price: -15%
Valuation: FAIR
```

Business Value açıklamaları ayrı bir state seti tanımlamaz. Fiyat düşüşü kendi başına ATTRACTIVE sonucu vermez; güncel fiyatın desteklenebilir değer aralığına göre konumu değerlendirilir.

### Update Flow

1. Önceki valuation'ın yöntemini, varsayımlarını ve güncelliğini incele.
2. Yeni material inputs'un business value üzerindeki etkisini market price değişiminden ayır.
3. Mevcut modelde yalnız gerekli inputs / assumptions'u güncelle; önceki ve yeni değer aralığını karşılaştır.
4. Reference price karşısında implied upside/downside, margin of safety ve valuation status'u değerlendir.
5. Confidence, freshness ve gerekli follow-up'ı belirt; recommendation'ı ayrı değerlendir.
6. Machine Record ve kısa Human Brief üret; yalnız gerekli protocol'lara yönlendir.

Material model değişikliği yoksa modelin korunduğu belirtilir; yalnız fiyat değişmişse fiyat karşılaştırması yenilenebilir. Sonuç üretmeye yetmeyen kanıt zorlanarak kesin bir valuation'a dönüştürülmez.

## Valuation Method and Margin of Safety

Tek bir yöntem bütün şirketlere zorunlu kılınmamalıdır. Şirkete göre uygun yöntem DCF, FCF yield / cash earnings, earnings multiples, EV/EBITDA, gerekçelendirildiğinde revenue multiples, sum-of-the-parts, scenario-based valuation veya ilgili olduğunda NAV olabilir.

Kullanılan methodology açıkça kaydedilmelidir. Mevcut yöntem korunabiliyorsa her run'da yeniden seçilmez; yöntem değişimi gerekiyorsa gerekçesi ve eski valuation ile karşılaştırma sınırlaması belirtilir. Kesin method selection kuralları henüz tasarlanmamıştır.

Gereksiz precision üretilmemelidir. Base valuation range ve ilgili olduğunda bear/base/bull scenarios tercih edilebilir; bunlar dayandıkları key assumptions ile birlikte sunulmalıdır. Implied upside/downside ve margin of safety'nin hangi değer aralığına / senaryoya dayandığı anlaşılır olmalı; olası getiri kesin sonuç gibi gösterilmemelidir.

Margin of safety konsept olarak kullanılabilir; tüm asset'lere aynı sabit threshold zorunlu kılınmaz. Risk, business quality, valuation uncertainty ve portfolio role'a göre değişebilir. Exact threshold ve framework açık tasarım soruları olarak kalır.

## Valuation Status and Recommendation

Mevcut valuation status seti **ATTRACTIVE, FAIR, EXPENSIVE** olarak korunur; yeni state eklenmez. Kesin status thresholds henüz tasarlanmamıştır. Freshness ve confidence, valuation status'tan ayrı değerlendirilir.

Güvenilir valuation üretilemiyorsa recommendation tarafında **REVIEW REQUIRED** kullanılabilir. Bu bir valuation state değildir. Eksik evidence FAIR anlamına gelmez; güncel status desteklenemiyorsa önceki status yeni doğrulanmış sonuç gibi sunulmaz. Eksik sonucun kesin temsili schema tasarımına bırakılır.

Mevcut recommendation seti **ADD, HOLD, REDUCE, SELL, REVIEW REQUIRED** olarak korunur. Recommendation; thesis, valuation, portfolio context ve ilgili olduğunda technical context birlikte değerlendirilerek oluşturulur. Valuation status recommendation değildir.

Aşağıdaki kurgusal boyut ayrımı örnekleri mümkündür:

```text
Thesis: INVALIDATED
Valuation: ATTRACTIVE
Recommendation: SELL
```

```text
Thesis: STRONGER
Valuation: EXPENSIVE
Recommendation: HOLD
```

İlk örnek ancak valuation'ın dayanakları ayrıca hâlâ güvenilir ise anlamlıdır; invalidated thesis'e bağlı eski valuation yeniden doğrulanmadan ATTRACTIVE kabul edilmez. Recommendation otomatik execution command değildir; final investment / action authority kullanıcıdadır. Boyut ayrımı [System Overview](../architecture/system-overview.md#recommendation-states) ile uyumlu kalır.

## Routing

| Bulgular | Olası yönlendirme |
|---|---|
| Assumptions thesis'e bağlı olarak değişmiş | Thesis Review context |
| Technical entry önemli | Technical Review |
| Portfolio concentration / sizing etkileniyor | Portfolio Monitoring / future Position Sizing logic için context |
| Valuation modeli artık güvenilir değil | Deeper research consideration / full rebuild ihtiyacı |

Her update bütün protocol'ları otomatik çalıştırmamalıdır. Tamamlanmış Thesis Review bulguları kullanılabilir; yeni bir thesis sorusu yoksa aynı review tekrar çalıştırılmak zorunda değildir. Önerilen follow-up, gerçekten tetiklenen protocol ve tamamlanan sonuç birbirinden ayrılır. Future Position Sizing logic burada tasarlanmaz veya çalıştırılmaz; yalnız ilgili etki kaydedilir.

## Outputs

Dual-output principle geçerlidir.

### Machine Record

Kesin schema: DESIGN PENDING. Konsept olarak compact kayıt şu bilgileri taşıyabilir:

- Protocol adı ve instrument
- Valuation date / timestamp
- Reference market price, fiyat tarihi ve para birimi
- Valuation methodology
- Previous valuation range
- Updated base valuation range
- Bear/base/bull scenarios, ilgili olduğunda
- Key assumptions ve key changed assumptions
- Business value değişimi ile market price değişiminin ayrımı
- Implied upside/downside
- Margin of safety
- Valuation status
- Confidence ve material evidence sınırlamaları
- Stale / fresh değerlendirmesi ve gerekçesi
- Recommendation ve kısa gerekçesi
- Required follow-up / open questions
- Triggered sub-protocols ve bekleyen sonuçlar
- Source/research references

Alan tipleri, zorunlulukları, database / JSON schema veya saklama yöntemi bu belgede belirlenmez.

### Human Brief

30–60 saniyede okunabilir, sade Türkçe ve değişiklik odaklı olmalıdır. Valuation status, recommendation, neyin değiştiği, tahmini değer aralığı, reference price ve gerekli aksiyon / follow-up yeterlidir. Kararı etkileyen freshness veya evidence sınırlaması varsa kısaca belirtilir.

Aşağıdaki yalnızca kurgusal tasarım örneğidir; rakamlar gerçek fiyat veya şirket valuation'ı değildir:

```text
ÖRNEK ŞİRKET — VALUATION UPDATE

Valuation: FAIR
Recommendation: HOLD

Ne değişti?
FCF beklentisi yükseldi; piyasa fiyatı da arttı.
Mevcut scenario-based valuation güncellendi.

Tahmini değer aralığı: 65–85 birim / hisse
Referans fiyat: 74 birim / hisse (örnek review tarihi)

Aksiyon:
Pozisyonu koru. Artırım değerlendirmesi için daha iyi margin of safety bekle.
```

## Architecture Relationship

Valuation Update, [Earnings Review](earnings-review.md) ve [Thesis Review](thesis-review.md) tarafından tetiklenebilen, [Single Asset Monitoring](single-asset-monitoring.md) tarafından çağrılabilen veya [Portfolio Monitoring](portfolio-monitoring.md) escalation sonucu çalışabilen asset-level specialist protocol'dür. Single Asset Monitoring tarafından çağrıldığında bulguları onun asset-level synthesis'ine girdi sağlar. Deep Research'in yerine geçmez.

Model representation, freshness, price source, scenario standards, margin-of-safety framework, confidence scoring, method selection ve full rebuild koşulları [Open Design Questions](../architecture/open-design-questions.md) içinde açık bırakılmıştır.
