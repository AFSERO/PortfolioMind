# Single Asset Monitoring

Status: DESIGN IN PROGRESS

## Purpose

Single Asset Monitoring, bir varlıkta material change tespit edildiğinde o varlığı daha detaylı inceleyen asset-level review protocolüdür.

- Bütün şirketi sıfırdan deep research etmez.
- Mevcut thesis ve önceki research'i başlangıç noktası olarak kullanır.
- Son incelemeden beri ne değiştiğini anlamaya çalışır.
- Gerektiğinde daha uzman alt protocol'lara yönlendirir.
- Sonuçları tek bir asset-level recommendation altında birleştirir.

Ana soru:

> Son incelemeden beri bu varlıkta yatırım kararımızı etkileyebilecek ne değişti?

## Typical Trigger

Genellikle şu kaynaklardan tetiklenebilir:

- Portfolio Monitoring
- News Monitoring
- Manual user request
- Major company-specific event
- Unusual price move with unclear cause
- Potential thesis deterioration
- Conflicting new evidence

Bu protocol normalde scheduled olarak bağımsız çalıştırılmak zorunda değildir. Bu belge yalnızca tasarım kaydıdır; aktif schedule veya gerçek monitoring içermez.

## Core Flow

Konsept olarak:

```text
Material Change Detected
        ↓
Load compact asset context
        ↓
What changed since last review?
        ↓
Classify the change
        ↓
Need specialized review?
        ├── Earnings → Earnings Review
        ├── Thesis issue → Thesis Review
        ├── Valuation issue → Valuation Update
        ├── Technical deviation → Technical Review
        └── Other company-specific event → analyze directly if lightweight
        ↓
Aggregate results
        ↓
Asset-level recommendation
```

## Important Efficiency Principle

Single Asset Monitoring bütün mevcut research dosyalarını her seferinde baştan okumamalıdır. Önce compact machine state kullanılmalıdır. Detaylı eski research report'larına yalnızca şu ihtiyaçlar için inilmelidir:

- Material ambiguity
- Contradiction
- Thesis-critical evidence
- Historical comparison

Amaç tekrar research'i ve context kullanımını azaltmaktır.

## Possible Inputs

Kesin schema henüz tasarlanmayacaktır. Konsept olarak şu bilgiler kullanılabilir:

- Asset identity
- Current position
- Current portfolio weight
- Latest thesis state
- Latest recommendation
- Latest valuation state
- Latest technical plan/status
- Last monitoring date
- Recent material events
- Open questions
- Relevant research references

## Possible Sub-Protocols

Gerektiğinde şu protocol'ları çağırabilir veya önerebilir:

- Earnings Review
- Thesis Review
- Valuation Update
- Technical Review
- Deep Research

Deep Research yalnızca mevcut evidence ciddi biçimde yetersizse veya şirket materially değişmişse kullanılmalıdır. Single Asset Monitoring'in varsayılan davranışı deep research değildir.

## Outputs

Dual-output principle geçerlidir.

### Machine Record

Kesin schema: DESIGN PENDING.

İleride aşağıdaki gibi state taşıyabilir:

- Asset
- Review date
- Material change
- Change category
- Thesis status
- Valuation status
- Technical status
- Recommendation
- Confidence
- Next action
- Triggered sub-protocols
- Open questions
- Source/research references

### Human Brief

Kullanıcı için kısa, sade ve mümkün olduğunca 30–60 saniyede okunabilir olmalıdır. Aşağıdaki yalnızca tasarım örneğidir; gerçek UBER analizi veya investment recommendation değildir:

```text
UBER — REVIEW COMPLETED

Thesis: WEAKER
Valuation: FAIR
Technical: ON TRACK
Recommendation: HOLD

Ne değişti?
Insurance maliyetleri beklenenden hızlı artıyor.

Aksiyon:
Pozisyonu koru.
Bir sonraki earnings'te insurance trendini tekrar kontrol et.
```

## Recommendation Relationship

Mevcut recommendation seti kullanılmalıdır: ADD, HOLD, REDUCE, SELL, REVIEW REQUIRED.

Recommendation; thesis, valuation, technical status ve portfolio context birlikte değerlendirilerek üretilmelidir. Tek bir veri noktası otomatik karar oluşturmamalıdır. Recommendation execution command değildir; final investment authority kullanıcıda kalır. Tanımlar ve boyut ayrımı [System Overview](../architecture/system-overview.md#recommendation-states) içinde kayıtlıdır.
