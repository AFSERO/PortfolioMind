# Technical Review

Status: DESIGN IN PROGRESS

## Purpose

Technical Review, fundamental research'in yerine geçmez. Amaç:

- Yatırım öncesi entry plan oluştururken fiyat davranışını değerlendirmek.
- Önemli support / resistance bölgelerini belirlemek.
- Trend yapısını incelemek.
- Staged entry bölgeleri oluşturmak.
- Olası technical invalidation bölgelerini kaydetmek.
- Pozisyon açıldıktan sonra güncel fiyat davranışını önceki teknik planla karşılaştırmak.

Technical analysis tek başına investment thesis oluşturmaz.

## Pre-Investment Use

Bir yatırım BUY CANDIDATE aşamasına geldikten ve portfolio fit değerlendirmesinden geçtikten sonra Technical Review kullanılabilir.

İncelenebilecek alanlar:

- Market structure
- Trend
- Major support zones
- Major resistance zones
- Volume
- Volatility
- Moving averages where useful
- RSI / momentum where useful
- Gaps
- Swing highs / lows
- ATR or similar volatility measures where useful
- Important historical price zones

Amaç tek bir kesin fiyat üretmek değildir. Çıktılar zone/range tabanlı olabilir. Konsept örneği:

```text
Preferred Entry Zone:
X–Y

Secondary Entry Zone:
A–B

Major Support:
...

Major Resistance:
...

Technical Invalidation / Review Zone:
...

Possible Profit-Taking / Reassessment Zone:
...
```

## Important Safety Principle

Technical levels otomatik trade command değildir. “Support kırıldı” tek başına SELL anlamına gelmemelidir; `TECHNICAL REVIEW REQUIRED` veya ilgili daha kapsamlı review protocol için trigger oluşturabilir. “RSI oversold” tek başına BUY sinyali değildir.

Technical analysis; fundamental thesis, valuation, portfolio fit ve risk ile birlikte değerlendirilmelidir.

## Technical Plan Persistence

Pozisyon açılmadan önce oluşturulan teknik plan ileride saklanmalıdır. Örnek bilgiler:

- Analysis date
- Reference price
- Trend expectation
- Entry zones
- Support zones
- Resistance zones
- Technical invalidation / review zones
- Volatility context
- Important chart observations
- Expected price-path assumptions
- Source/chart reference

Kesin database/schema henüz tasarlanmayacaktır.

## Relationship With Portfolio Monitoring

Weekly Portfolio Monitoring sırasında full technical analysis her pozisyon için baştan yapılmamalıdır. Cheap Pre-Check kapsamında şu soru kontrol edilebilir:

> Güncel fiyat davranışı önceki technical plan'dan materially sapmış mı?

Aşağıdakiler konsept örnekleridir; gerçek analiz veya işlem kararı değildir:

```text
Previous Technical Plan:
Bullish structure
Major support: X–Y

Current:
Price remains above support
Trend structure intact

Technical Status:
ON TRACK

Action:
NONE
```

```text
Previous Technical Plan:
Major support: X–Y

Current:
Support broken with unusual volume

Technical Status:
DEVIATED

Action:
TECHNICAL REVIEW REQUIRED
```

## Technical Status

Şimdilik yalnız konsept olarak:

- ON TRACK
- NEUTRAL
- DEVIATED
- REVIEW REQUIRED

Bunlar final investment recommendation değildir. Kesin state definitions daha sonra tasarlanacaktır.

## Relationship With Recommendation

Portfolio recommendation ve technical status ayrı tutulmalıdır. Aşağıdakiler yalnızca bu ayrımı gösteren örneklerdir; otomatik recommendation üretme kuralları değildir:

```text
Thesis: UNCHANGED
Valuation: ATTRACTIVE
Technical Status: DEVIATED
Recommendation: REVIEW REQUIRED
```

```text
Thesis: STRONGER
Valuation: ATTRACTIVE
Technical Status: ON TRACK
Recommendation: ADD
```

Şimdilik kabul edilen ana recommendation seti ADD, HOLD, REDUCE, SELL ve REVIEW REQUIRED'dır; tanımlar ve analiz boyutlarından ayrım [System Overview](../architecture/system-overview.md#recommendation-states) içinde kayıtlıdır. Recommendation execution command değildir; final investment authority kullanıcıda kalır.

## Outputs

Mevcut dual-output principle geçerlidir.

- Machine Record: DESIGN PENDING
- Human Brief: DESIGN PENDING
