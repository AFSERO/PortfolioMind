# Context Builders — MVP Part 4A

Status: IMPLEMENTED (Part 4A: Asset Context Builder)

AI protokollerinin her çalıştırmada bütün veritabanını, bütün araştırma klasörünü veya sınırsız geçmişi okumasını önlemek için tasarlanmış application-kontrollü, kompakt ve JSON-serializable context katmanı (`investment_intelligence.context`).

```text
Persistent State (Instrument, IntelligenceState)
+
Recent History (Bounded ProtocolRuns)
+
Research References (Bounded ResearchArtifacts)
+
Active Technical Plan (Only Active TechnicalPlan)
       ↓
Context Builder (investment_intelligence.context)
       ↓
Compact JSON-ready Context
       ↓
Future AI Protocol (Part 4B)
```

## 1. Asset Context Yapısı (`build_asset_context`)

```json
{
  "instrument": {
    "id": "uuid-string",
    "symbol": "UBER",
    "name": "Uber Technologies, Inc.",
    "instrument_type": "equity",
    "venue": "NYSE",
    "currency": "USD"
  },
  "intelligence_state": {
    "thesis_status": "STRONGER",
    "valuation_status": "ATTRACTIVE",
    "technical_status": "ON_TRACK",
    "recommendation": "ADD",
    "last_review_at": "2026-09-15T12:00:00+00:00",
    "last_monitoring_at": null,
    "next_review_at": "2026-09-22T12:00:00+00:00"
  },
  "active_technical_plan": {
    "id": "uuid-string",
    "reference_at": "2026-09-15T12:00:00+00:00",
    "reference_price": 75.50,
    "trend_expectation": "Breakout towards ATH",
    "entry_zones": [{"low": 72.0, "high": 75.0}],
    "support_zones": [{"level": 70.0}],
    "resistance_zones": [{"level": 82.0}],
    "review_or_invalidation_zones": [{"level": 67.5}],
    "profit_taking_or_reassessment_zones": [{"level": 90.0}],
    "notes": "Current tactical plan"
  },
  "recent_protocol_runs": [
    {
      "id": "uuid-string",
      "protocol_name": "thesis_review",
      "status": "COMPLETED",
      "started_at": "2026-09-15T12:00:00+00:00",
      "completed_at": "2026-09-15T12:05:00+00:00",
      "machine_record": {"summary": "..."},
      "human_brief": "Thesis stronger on improved mobility margins.",
      "confidence": "HIGH"
    }
  ],
  "research_artifacts": [
    {
      "id": "uuid-string",
      "artifact_type": "research_memo",
      "path": "research/UBER/2026-09-15/memo.md",
      "version": "v2",
      "created_at": "2026-09-15T12:00:00+00:00",
      "protocol_run_id": "uuid-string",
      "artifact_metadata": {"source": "10-Q"}
    }
  ]
}
```

## 2. Default Limitler ve Boyut Disiplini
- **Recent Protocol Runs:** `runs_limit: int = 5` (yalnızca o enstrümana ait en güncel run'lar).
- **Research Artifacts:** `artifacts_limit: int = 5` (yalnızca o enstrümana ait en güncel referanslar; dosya içerikleri okunmaz).
- **Technical Plan:** Yalnızca **aktif** olan plan eklenir; geçmiş pasif planlar elenir. Aktif plan yoksa `null` döner.
- **Missing State:** Yeni oluşturulmuş ve henüz state/plan/history'si bulunmayan enstrümanlarda builder hata vermez; `intelligence_state: null`, `active_technical_plan: null`, boş listeler döner.
- **Cross-Instrument İzolasyonu:** Başka enstrümanlara veya portföy seviyesine ait kayıtlar filtrelenir; context'e sızamaz.

## 3. Serialization
- Çıktı doğrudan Python primitive tipleri (`str`, `float`, `int`, `dict`, `list`, `None`) içerir.
- Standart kütüphane `json.dumps(context)` ile doğrudan hatasız serialize edilir.
- Yardımcı `serialize_context(context, indent=...)` fonksiyonu da mevcuttur.
- UUID'ler string, datetime'lar UTC ISO-8601, enum'lar string değer, Decimal'lar float olarak normalize edilir.

