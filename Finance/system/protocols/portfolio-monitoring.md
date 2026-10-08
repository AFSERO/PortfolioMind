# Portfolio Monitoring

Status: DESIGN IN PROGRESS

## Trigger Model

Portfolio Monitoring gelecekte şu trigger'larla çalışabilir:

- Weekly scheduled review
- Manual user request
- Event-driven review: önemli bir olay başka protocol tarafından tetiklendiğinde

Preferred normal cadence: **Weekly**.

SCHEDULE STATUS: NOT ACTIVE

Bu belge yalnızca onaylanmış tasarım kararlarını kaydeder; implementation, aktif schedule veya gerçek monitoring içermez.

## Cheap Pre-Check

Weekly Portfolio Monitoring bütün pozisyonları baştan deep research etmemelidir. Önce portfolio ve son monitoring state okunarak düşük maliyetli bir Cheap Pre-Check çalıştırılmalıdır.

Amaç:

> Son monitoring tarihinden beri hangi pozisyonlarda gerçekten decision-relevant bir değişiklik olduğunu bulmak.

Her pozisyon için ilk aşamada kontrol edilebilecek başlıklar:

- New earnings / financial results
- Major news
- Guidance change
- Important company disclosure
- Thesis trigger / invalidation signal
- Major valuation change
- Unusual price move
- Relevant regulatory development
- Material competitive development
- Compare current price behavior against stored technical plan

Bu liste nihai değildir; ileride detaylandırılacaktır.

Material technical deviation, [Technical Review](technical-review.md) için trigger olabilir. Weekly Portfolio Monitoring her pozisyon için full technical analysis'i baştan yapmamalıdır.

## Routing Principle

### No Material Change

Pozisyon için pahalı analiz yapılmaz. Durum kısa şekilde `NO MATERIAL CHANGE / SKIP` olarak işaretlenebilir.

### Material Change Detected

İlgili alt protocol çağrılması önerilir. Örnek yönlendirmeler:

```text
New earnings
→ Earnings Review

Major company-specific development
→ Single Asset Monitoring

Potential thesis deterioration
→ Thesis Review

Large valuation change
→ Valuation Update
```

Kesin routing kuralları daha sonra tasarlanacaktır.

## Important Price-Move Rule

Unusual price movement tek başına BUY / SELL / ADD / REDUCE sinyali değildir. Büyük fiyat hareketi yalnızca şu soruyu tetikleyebilir:

> Neden oldu ve investment thesis / valuation açısından önemli mi?

Sebep bulunamazsa veya material değilse daha ileri research yapılması zorunlu değildir.

## Example Flow

Konsept örneğidir; gerçek portföy veya monitoring sonucu değildir:

```text
Weekly Portfolio Monitoring
        ↓
Read portfolio + last monitoring state
        ↓
Cheap Pre-Check
        ↓
10 positions

7 → no material change → skip
1 → earnings → Earnings Review
1 → major news → Single Asset Monitoring
1 → unusual price move → investigate cause / possible Valuation Update
        ↓
Collect protocol results
        ↓
Machine Record
+
Human Brief
```

## Efficiency Principle

Pahalı analiz yalnızca Cheap Pre-Check'in potansiyel olarak decision-relevant bir değişiklik tespit ettiği varlıklar için tetiklenmelidir. Amaç repeated research ve Codex/model usage azaltmak, monitoring'i ölçeklenebilir kılmak ve user-facing noise azaltmaktır.

## Outputs

Mevcut dual-output principle geçerlidir.

- Machine Record: DESIGN PENDING
- Human Brief: DESIGN PENDING
