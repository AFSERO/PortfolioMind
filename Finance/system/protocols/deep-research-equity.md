# Deep Research — Equities (Stocks) [Decision Model v2]

Status: ACTIVE PROTOCOL

## Purpose

Deep Research for Equities establishes a rigorous, evidence-grounded investment case for individual corporate equities (BIST and Global Equities).
Its purpose is to produce a structured, defensible investment judgment, identify competitive moats, evaluate reported accounting against cash flow reality, establish an intrinsic valuation anchor, and arrive at a clear directional recommendation (`ADD`, `HOLD`, `REDUCE`, `SELL`).

## Core Product Principle: Decisive Judgment

Deep Research exists to synthesize evidence into an explicit investment view.
- **Normal Output**: Must be a directional recommendation: `ADD`, `HOLD`, `REDUCE`, or `SELL`.
- **Uncertainty**: Represent uncertainty through `confidence` (0–100), NEVER through `REVIEW_REQUIRED`. Every investment decision contains uncertainty; the model must state what it thinks.
- **REVIEW_REQUIRED Restriction**: `REVIEW_REQUIRED` is strictly an exception. It is only permitted when the system genuinely cannot form a defensible view due to missing critical SEC/KAP filings, unresolvable source conflicts, or incomplete protocol execution. If `REVIEW_REQUIRED` is emitted, `review_required_reason` is MANDATORY.
- **Technical Analysis Independence**: Technical structure is one input among several. An indeterminate or deviated technical status (`REVIEW_REQUIRED` or `DEVIATED`) must NOT block or override the fundamental investment recommendation.

## Research Dimensions

### 1. Business Model & Competitive Moat
- Value proposition, unit economics, and structural barriers to entry (switching costs, network effects, cost advantage, patents/intangibles).
- Market share trajectory, industry structure, and competitive dynamics.

### 2. Financial Quality & Economic Reality
- Revenue growth quality (organic volume vs. price/inflation pass-through).
- Margin durability and operating leverage (Gross, EBITDA, Operating margins across economic cycles).
- Cash conversion quality: Operating Cash Flow and Free Cash Flow (FCF) conversion versus reported Net Income.
- Capital intensity, maintenance vs. growth Capex, working capital trends.
- Balance sheet strength: Net Debt / EBITDA, debt maturity wall, interest coverage ratio, liquidity buffer.

### 3. Intrinsic Valuation Anchor
- Equity valuation status: `ATTRACTIVE | FAIR | EXPENSIVE`.
- Multiples vs. historical 5-year median and industry peers (EV/EBITDA, P/E, FCF Yield, P/B).
- DCF / conservative earnings power yield and margin of safety at current market price.

### 4. Thesis Invalidation & Catalysts
- Near-to-medium term fundamental catalysts.
- Explicit invalidation triggers: Concrete operational or balance-sheet deterioration that breaks the investment case.

## Thesis → Recommendation Consistency Rules

1. `STRONGER` thesis → `ADD` or `HOLD`.
2. `UNCHANGED` thesis → `ADD`, `HOLD`, or `REDUCE` based on valuation and risk.
3. `WEAKER` thesis → `HOLD` or `REDUCE`.
4. `INVALIDATED` thesis → `REDUCE` or `SELL`. (Never `ADD`; never generic `REVIEW_REQUIRED` without missing evidence).
5. `ATTRACTIVE` valuation + `SELL` is contradictory unless thesis is `INVALIDATED` or catastrophic balance-sheet risk is identified.
6. `EXPENSIVE` valuation + `ADD` requires exceptional catalyst justification.

## Output Schema Requirements

The AI engine must output clean JSON matching the following contract:

```json
{
  "thesis_status": "STRONGER | UNCHANGED | WEAKER | INVALIDATED",
  "valuation_status": "ATTRACTIVE | FAIR | EXPENSIVE",
  "technical_status": "ON_TRACK | NEUTRAL | DEVIATED | REVIEW_REQUIRED",
  "recommendation": "ADD | HOLD | REDUCE | SELL | REVIEW_REQUIRED",
  "confidence": 78,
  "primary_reason": "Clear 1-2 sentence core reason for this directional recommendation.",
  "supporting_reasons": [
    "Key fundamental driver 1",
    "Key fundamental driver 2"
  ],
  "key_risks": [
    "Primary risk factor 1",
    "Primary risk factor 2"
  ],
  "what_would_change_my_view": "Specific metrics, earnings thresholds, or events that would trigger a rating upgrade/downgrade.",
  "evidence_gaps": [
    "Any disclosure or data limitations identified during research (leave empty if none)"
  ],
  "review_required_reason": null,
  "human_brief": "SONUÇ\n\nÖNERİ:\nADD\n\nGÜVEN:\n78%\n\nNEDEN?\nİş modeli yüksek serbest nakit akışı üretmeye devam ediyor ve mevcut değerleme cazip bir güvenlik marjı sunuyor.\n\nNE DEĞİŞTİ?\nOperasyonel marjlar beklentileri aştı; borçluluk çarpanı 1.8x seviyesine geriledi.\n\nRİSKLER\n- Hammadde maliyetlerinde olası artış\n- İhracat pazarlarındaki yavaşlama\n\nBU GÖRÜŞÜ NE DEĞİŞTİRİR?\nFAVÖK marjının %15 altına inmesi veya pazar payı kaybı görüşü nötrler.\n\nEKSİK VERİ\nSon çeyrek segment kırılım detayları kamuya açıklanmamıştır.",
  "comprehensive_synthesis": "Comprehensive deep-dive analysis of business quality, financial statements, valuation anchors, and competitive position.",
  "material_changes": [
    "List of structural drivers, fundamental changes, or margin shifts identified"
  ],
  "open_questions": [
    "Critical variables to monitor in upcoming earnings or SEC/KAP filings"
  ]
}
```
