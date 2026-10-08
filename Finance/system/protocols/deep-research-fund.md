# Deep Research — Funds (Mutual Funds, TEFAS & ETFs) [Decision Model v2]

Status: ACTIVE PROTOCOL

## Purpose

Deep Research for Funds analyzes pooled investment vehicles such as Turkish TEFAS mutual funds (Hisse Senedi Yoğun Fonlar, Değişken Fonlar, Borçlanma Araçları, Serbest Fonlar) and global ETFs (e.g. SPY, QQQ, VT).
Funds are NOT single operating corporations; they are managed portfolios governed by an investment mandate, portfolio managers, fee structures, regulatory rules, and liquidity/valör conditions.

## Core Fund Decision Principles

1. **NAV is NOT an Intrinsic Valuation Target**:
   A mutual fund does not have a corporate P/E or DCF target. Do not display a misleading `FAIR` valuation placeholder.
2. **Distinguish Underlying Valuation from Fund Quality**:
   - **Underlying Portfolio Valuation**: Are the underlying assets/sectors held by the fund cheap or expensive? (`ATTRACTIVE | FAIR | EXPENSIVE | UNKNOWN | N_A`)
     - **CRITICAL RULE**: Only assign ATTRACTIVE / FAIR / EXPENSIVE if there is sufficient verified evidence about the underlying portfolio or asset universe. If current portfolio holdings / allocation / benchmark valuation cannot be established reliably: `underlying_valuation = UNKNOWN`. Never guess or default to `FAIR`.
   - **Fund Quality & Manager Attractiveness**: Is the fund manager executing the mandate skillfully, controlling risk, generating alpha, and justifying fees? (`STRONG | ACCEPTABLE | WEAK | POOR | UNKNOWN`)
     - For a fund under operational, default, regulatory, or liquidation stress, fund quality is `POOR` even when underlying valuation is `UNKNOWN`.
3. **Decisive Investment View**:
   Deep Research must produce a clear stance: `ADD`, `HOLD`, `REDUCE`, or `SELL`.
   `REVIEW_REQUIRED` is strictly reserved for critical evidence breakdown/data conflict and requires `review_required_reason`.
4. **Execution Status is Independent from Investment View**:
   Separate the directional view from implementation feasibility:
   - `execution_status`: `AVAILABLE | RESTRICTED | BLOCKED | UNKNOWN`
   - *Example*: A fund in liquidation or redemption default has Investment View `SELL` and Execution Status `RESTRICTED` or `BLOCKED`. Do NOT convert `SELL` to `HOLD` or `REVIEW_REQUIRED` simply because sales are restricted!
5. **Technical Analysis Applicability**:
   For mutual funds under liquidation, redemption suspension, transaction freeze, or default: `technical_status = N_A`. Do NOT produce `NEUTRAL` simply because technical analysis was omitted.
6. **Confidence Calibration**:
   Confidence in directional investment view (0–100) must be calibrated against evidence gaps. If material gaps remain (e.g. unverified holdings, uncertain recovery), confidence must be calibrated downwards (e.g. 55–80), and secondary certainty fields should be populated:
   - `recovery_value_confidence`: `LOW | MEDIUM | HIGH | UNKNOWN`
   - `execution_confidence`: `LOW | MEDIUM | HIGH | UNKNOWN`

## Output Schema Requirements

The AI engine must output clean JSON matching the following contract:

```json
{
  "thesis_status": "STRONGER | UNCHANGED | WEAKER | INVALIDATED",
  "valuation_status": "ATTRACTIVE | FAIR | EXPENSIVE | UNKNOWN | N_A",
  "technical_status": "ON_TRACK | PULLBACK | EXTENDED | BREAKDOWN | REVIEW_REQUIRED | UNKNOWN | N_A",
  "recommendation": "ADD | HOLD | REDUCE | SELL | REVIEW_REQUIRED",
  "execution_status": "AVAILABLE | RESTRICTED | BLOCKED | UNKNOWN",
  "confidence": 75,
  "recovery_value_confidence": "LOW | MEDIUM | HIGH",
  "execution_confidence": "LOW | MEDIUM | HIGH",
  "data_quality_score": 60,
  "assessment_type": "FUND",
  "underlying_valuation": "ATTRACTIVE | FAIR | EXPENSIVE | UNKNOWN | N_A",
  "fund_quality": "STRONG | ACCEPTABLE | WEAK | POOR | UNKNOWN",
  "fund_attractiveness": "ATTRACTIVE | NEUTRAL | UNATTRACTIVE | UNKNOWN",
  "primary_reason": "Clear 1-2 sentence core reason for this directional recommendation.",
  "supporting_reasons": [
    "Key performance or portfolio driver 1",
    "Key fee or manager driver 2"
  ],
  "key_risks": [
    "Primary risk factor 1",
    "Primary risk factor 2"
  ],
  "what_would_change_my_view": "Specific benchmark-relative recovery or allocation changes that would upgrade/downgrade this view.",
  "evidence_gaps": [
    "Any portfolio disclosure limitations (e.g. monthly TEFAS portfolio delay or liquidation recovery unknown)"
  ],
  "review_required_reason": null,
  "human_brief": "SONUÇ\n\nÖNERİ:\nSELL\n\nUYGULANABİLİRLİK:\nŞu anda kısıtlı / engelli (RESTRICTED)\n\nGÜVEN:\nYatırım görüşüne güven: %75 (YÜKSEK)\n\nTAHSİLAT / GERİ KAZANIM BELİRSİZLİĞİ:\nDÜŞÜK GÜVEN (Tahsilat süreci ve nihai pay değeri belirsizdir)\n\nNEDEN?\nFonun tasfiye/temerrüt durumu yatırım tezini tamamen geçersiz kılmıştır.\n\nNE DEĞİŞTİ?\nFon işlemleri durdurulmuş, itfa takvimi kilitlenmiştir.\n\nRİSKLER\n- Hukuki/icra süreçlerinden doğan nihai tahsilat kaybı\n- Uzun vadeli sermaye blokajı\n\nBU GÖRÜŞÜ NE DEĞİŞTİRİR?\nFon yönetiminin net bir itfa takvimi açıklaması ve temerrüdün çözülmesi.\n\nEKSİK VERİ\nNihai kurtarma oranı ve nakit dağıtım tarihi bilinmemektedir.",
  "comprehensive_synthesis": "Comprehensive review of fund mandate, manager execution, liquidation status, and execution feasibility.",
  "material_changes": [
    "Noteworthy shifts in top holdings, manager changes, or redemption status"
  ],
  "open_questions": [
    "Key monitoring questions regarding liquidation timeline or asset recovery"
  ]
}
```
