# Deep Research — Physical Gold & Precious Metals [Decision Model v2]

Status: ACTIVE PROTOCOL

## Purpose

Deep Research for Physical Gold and Precious Metals evaluates physical bullion (Gram Altın, Çeyrek/Cumhuriyet, Külçe), exchange-traded gold, and precious metal holdings.
Gold has zero default risk, produces no cash flows or dividends, and cannot go bankrupt. It functions as a monetary anchor, safe-haven asset, and hedge against fiat currency debasement and geopolitical turmoil. Research focuses on real yields, central bank reserve purchases, currency dynamics (USD/TRY), and physical liquidity/spreads.

## Core Precious Metals Decision Principles

1. **Valuation Means Macro Attractiveness**:
   Gold has no P/E or discounted cash flows. Do not pretend gold has an equity-style intrinsic fair value, and do not call it `FAIR` simply because no stock valuation exists. Instead, evaluate **Macro Attractiveness**:
   - `ATTRACTIVE`: Negative/falling real interest rates, strong central bank accumulation, accelerating fiat debasement, rising geopolitical risk premium.
   - `NEUTRAL`: Stable real yields, balanced central bank flows, consolidation after major macro repricing.
   - `UNATTRACTIVE`: Sustained regime of sharply rising positive real rates, strong USD/DXY, coordinated central bank net selling.
2. **Decisive Recommendation**:
   For held gold/precious metals positions, output must normally be: `ADD`, `HOLD`, `REDUCE`, or `SELL`.
   Uncertainty is captured in `confidence` (0–100).
   `REVIEW_REQUIRED` is strictly an exception requiring `review_required_reason`.
3. **Technical Analysis Context**:
   Technical price action provides timing context, but an indeterminate technical status must NOT cause a final `REVIEW_REQUIRED`.
4. **Thesis Consistency**:
   - `STRONGER` thesis → `ADD` or `HOLD`.
   - `UNCHANGED` thesis → `ADD`, `HOLD`, or `REDUCE` based on macro regime and portfolio hedge sizing.
   - `WEAKER` thesis → `HOLD` or `REDUCE`.
   - `INVALIDATED` thesis → `REDUCE` or `SELL`.

## Research Dimensions

### 1. Macro-Monetary Environment
- Real interest rate dynamics: Correlation with US 10-Year Real Yields (TIPS).
- US Dollar Index (DXY) trajectory and global fiat expansion (Global M2).
- Global sovereign debt sustainability and fiscal deficit pressures.

### 2. Central Bank & Institutional Demand
- Net official central bank purchases (TCMB, PBoC, emerging market central banks).
- De-dollarization trends and reserve diversification into physical bullion.
- Physical ETF flows (sustained inflows vs. persistent liquidations).

### 3. Safe Haven & Geopolitical Risk Premium
- Regional or global geopolitical conflict escalation.
- Systemic banking sector fragility and sovereign credit concerns.
- Stagflation risk (sticky inflation accompanied by slowing economic growth).

### 4. Local Currency Dynamics & Purchasing Power (Turkish Context)
- Dual-engine Gram Gold pricing formula: `(Ons Altın USD / 31.1035) * USD/TRY`.
- Domestic purchasing power preservation against Turkish inflation (TÜFE/ENAG).
- Kapalıçarşı physical spread: Bank gold account spreads vs. physical delivery premiums in the Grand Bazaar.

### 5. Invalidation Criteria
- Sustained multi-year regime of positive, rising real interest rates without geopolitical risk.
- Coordinated global central bank net reserve liquidations.
- Global deflationary crunch.

## Output Schema Requirements

The AI engine must output clean JSON matching the following contract:

```json
{
  "thesis_status": "STRONGER | UNCHANGED | WEAKER | INVALIDATED",
  "valuation_status": "ATTRACTIVE | FAIR | EXPENSIVE",
  "technical_status": "ON_TRACK | NEUTRAL | DEVIATED | REVIEW_REQUIRED",
  "recommendation": "ADD | HOLD | REDUCE | SELL | REVIEW_REQUIRED",
  "confidence": 85,
  "assessment_type": "PRECIOUS_METALS",
  "macro_regime": "FAVORABLE | NEUTRAL | UNFAVORABLE",
  "macro_attractiveness": "ATTRACTIVE | NEUTRAL | UNATTRACTIVE",
  "primary_reason": "Clear 1-2 sentence core reason for this directional recommendation.",
  "supporting_reasons": [
    "Key macro or central bank driver 1",
    "Key currency or physical spread driver 2"
  ],
  "key_risks": [
    "Primary risk factor 1",
    "Primary risk factor 2"
  ],
  "what_would_change_my_view": "Specific real yield or central bank policy shifts that would upgrade/downgrade this view.",
  "evidence_gaps": [
    "Any data limitations identified (leave empty if none)"
  ],
  "review_required_reason": null,
  "human_brief": "SONUÇ\n\nÖNERİ:\nHOLD\n\nGÜVEN:\n85%\n\nNEDEN?\nMerkez bankası alımları ve USD/TRY kur dinamikleri güçlü bir koruma kalkanı sağlamaya devam etmektedir; küresel reel faiz ortamı nötr-pozitif dengededir.\n\nNE DEĞİŞTİ?\nOns bazında direnç test edilirken yerel fiziki Kapalıçarşı makas aralığı normal bantta seyretmektedir.\n\nRİSKLER\n- ABD tahvil faizlerinde beklenmedik sıçrama\n- Küresel jeopolitik gerilimlerde geçici yatışma\n\nBU GÖRÜŞÜ NE DEĞİŞTİRİR?\nABD 10 yıllık reel faizlerinin kalıcı biçimde %2.5 üzerine yerleşmesi ve merkez bankası alımlarının durması durumunda REDUCE değerlendirilir.\n\nEKSİK VERİ\nBelirgin veri eksiği bulunmamaktadır.",
  "comprehensive_synthesis": "In-depth strategic breakdown of real rate trajectory, central bank gold reserves, USD/TRY currency cushion, and physical holding terms.",
  "material_changes": [
    "Key shifts in real rates, central bank gold accumulation, or physical market premiums"
  ],
  "open_questions": [
    "Critical macro and central bank signals to monitor"
  ]
}
```
