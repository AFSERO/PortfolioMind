# Deep Research — Crypto & Digital Assets [Decision Model v2]

Status: ACTIVE PROTOCOL

## Purpose

Deep Research for Crypto evaluates native blockchain protocols, digital commodities (e.g. Bitcoin), decentralized finance (DeFi), and tokenized infrastructure.
Unlike traditional equities, crypto assets do not report corporate net income or statutory P/E ratios. Research focuses on monetary properties, tokenomics, supply dilution schedules, network adoption, on-chain economics, liquidity dynamics, and market structure.

## Core Crypto Decision Principles

1. **Valuation Means Market / Network Attractiveness**:
   Do NOT apply stock valuation logic (P/E, DCF). Instead, evaluate **Market & Network Attractiveness**:
   - `ATTRACTIVE`: High network adoption, favorable supply/issuance dynamics, healthy liquidity, low/moderate cycle positioning.
   - `NEUTRAL`: Balanced risk/reward, fair cycle positioning, steady adoption without major catalysts.
   - `UNATTRACTIVE`: Heavy upcoming token unlock cliffs, declining active users, predatory dilution, or overheated cycle positioning.
2. **Decisive Recommendation**:
   For held crypto positions, output must normally be: `ADD`, `HOLD`, `REDUCE`, or `SELL`.
   Uncertainty is captured via `confidence` (0–100).
   `REVIEW_REQUIRED` is strictly an exception requiring `review_required_reason` (e.g. unverified smart contract exploit or hard fork ambiguity).
3. **Technical Analysis Context**:
   Technical market structure (key support/resistance, funding rates, open interest) is important context for crypto timing, but an indeterminate technical status must NOT automatically trigger `REVIEW_REQUIRED`.
4. **Thesis Consistency**:
   - `INVALIDATED` thesis → `REDUCE` or `SELL`.
   - `WEAKER` thesis → `HOLD` or `REDUCE`.
   - `UNCHANGED` thesis → `ADD`, `HOLD`, or `REDUCE` based on cycle valuation and dilution risk.
   - `STRONGER` thesis → `ADD` or `HOLD`.

## Research Dimensions

### 1. Network Purpose & Value Proposition
- Monetary store of value (e.g. BTC), L1/L2 smart contract platform, DeFi infrastructure, or governance.
- Developer ecosystem momentum (GitHub commits, tooling, active developers).
- Real economic traction vs. temporary incentive/farming volume.

### 2. Tokenomics, Supply Dynamics & Dilution
- Token design: Fee-accrual, burning mechanism (EIP-1559 style), work token, or non-productive governance token.
- Circulating vs Max Supply (FDV / Market Cap ratio).
- Emission schedule, inflation rate, and impending unlock/vesting cliffs.

### 3. On-Chain Activity & Network Health
- Daily active addresses/users (DAU) and transaction count trends.
- Total Value Locked (TVL) and Capital Efficiency (Volume / TVL).
- Economic fee generation: Real user fees paid vs protocol subsidies spent.
- Security architecture: PoW hash rate / PoS validator decentralization (Nakamoto coefficient).

### 4. Market Structure, Derivatives & Macro Sensitivity
- Exchange liquidity, orderbook depth, and custody reserves.
- Derivatives positioning: Funding rates, open interest (OI), long/short liquidations.
- Correlation with global liquidity (M2), US dollar (DXY), and interest rate regimes.

### 5. Regulatory & Security Invalidation Criteria
- Regulatory standing (SEC/MiCA status, SPK regulations).
- Smart contract audit track record and exploit history.
- Invalidation triggers: Protocol exploit, critical governance failure, predatory dilution, regulatory prohibition.

## Output Schema Requirements

The AI engine must output clean JSON matching the following contract:

```json
{
  "thesis_status": "STRONGER | UNCHANGED | WEAKER | INVALIDATED",
  "valuation_status": "ATTRACTIVE | FAIR | EXPENSIVE",
  "technical_status": "ON_TRACK | NEUTRAL | DEVIATED | REVIEW_REQUIRED",
  "recommendation": "ADD | HOLD | REDUCE | SELL | REVIEW_REQUIRED",
  "confidence": 82,
  "assessment_type": "CRYPTO",
  "network_adoption": "EXPANDING | STABLE | CONTRACTING",
  "market_attractiveness": "ATTRACTIVE | NEUTRAL | UNATTRACTIVE",
  "primary_reason": "Clear 1-2 sentence core reason for this directional recommendation.",
  "supporting_reasons": [
    "Key on-chain or tokenomics driver 1",
    "Key market structure driver 2"
  ],
  "key_risks": [
    "Primary risk factor 1",
    "Primary risk factor 2"
  ],
  "what_would_change_my_view": "Specific on-chain metrics or macro shifts that would upgrade/downgrade this view.",
  "evidence_gaps": [
    "Any on-chain data limitations identified (leave empty if none)"
  ],
  "review_required_reason": null,
  "human_brief": "SONUÇ\n\nÖNERİ:\nHOLD\n\nGÜVEN:\n82%\n\nNEDEN?\nZincir üstü kullanıcı aktivitesi ve arz dinamikleri güçlü seyrini korumaktadır; mevcut döngü seviyesi dengeli bir risk-getiri profili sunmaktadır.\n\nNE DEĞİŞTİ?\nKısa vadeli türev piyasasında açık pozisyonlar (OI) normalleşti; borsa rezervlerindeki düşüş trendi devam ediyor.\n\nRİSKLER\n- Küresel makro likidite daralması\n- Olası regülasyon baskıları\n\nBU GÖRÜŞÜ NE DEĞİŞTİRİR?\nAktif adres sayısında %20+ daralma veya kritik teknik destek seviyesinin kalıcı kırılması durumunda REDUCE değerlendirilir.\n\nEKSİK VERİ\nBelirgin veri eksiği bulunmamaktadır.",
  "comprehensive_synthesis": "Comprehensive deep-dive analysis of network adoption, tokenomics dilution, on-chain metrics, and derivative market structure.",
  "material_changes": [
    "Key shifts in on-chain metrics, token unlocks, or governance developments"
  ],
  "open_questions": [
    "Critical on-chain or market indicators to monitor"
  ]
}
```
