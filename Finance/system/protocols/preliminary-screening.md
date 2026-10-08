# Preliminary Screening

Status: CORE DESIGN DEFINED / NOT IMPLEMENTED

## Purpose and Role

Preliminary Screening, ayrı ve lightweight bir research gate'tir.

> Bu candidate pahalı Deep Research aşamasına girmeye gerçekten değer mi?

```text
Opportunity Discovery → Preliminary Screening → DEEP RESEARCH / WATCH / REJECT
```

[Opportunity Discovery](opportunity-discovery.md) aday bulur; bu gate araştırma maliyetine değip değmediğini değerlendirir. Replacement Candidate'dan gelen yeni adaylar da aynı gate'ten geçebilir. Discovery'deki preliminary verdict, screening tamamlanmadıysa bu gate'i geçmiş sayılmaz. Mevcut güncel screening kanıtı kullanılabilir; aynı çalışma tekrarlanmaz.

## Scope and Flow

Önce compact candidate record, önceki screening / research references, why now ve ilgili portfolio context okunur. Konsept inceleme alanları:

- Basic business quality
- Rough growth profile
- Rough valuation
- Obvious risks
- Catalyst / why now
- Portfolio relevance
- Data / evidence availability

Ucuz ve sınırlı screening ile bariz zayıflıklar, araştırma değeri ve kanıt boşlukları belirlenir. Full company research, ayrıntılı valuation veya bütün marketi yeniden tarama yapılmaz. Rough valuation tamamlanmış valuation değildir; portfolio relevance da sonraki Portfolio Fit gate'inin yerine geçmez.

## Outcomes and Handoff

- **DEEP RESEARCH:** Daha pahalı evidence / reasoning çalışmasına değer; güçlü gerekçe ve cevaplanacak kritik sorular [Deep Research](deep-research.md)'e aktarılır.
- **WATCH:** İlerlemek için gerekli gelişme veya evidence belirtilir.
- **REJECT:** Mevcut kapsamda araştırma maliyetine değmiyor; kısa gerekçe kaydedilir.

Eksik evidence olumlu varsayılmaz. Screening thresholds ve kesin karar kuralları açık kalır; aday kotası yoktur. Sonuçlar research-stage verdict'tir; yatırım recommendation'ı, otomatik Deep Research çalıştırma veya trade command değildir.

## Outputs

Machine Record konsept olarak instrument, screening date, candidate / context references, kısa bulgular, rough valuation, riskler, evidence boşlukları, verdict, confidence, next step ve source references taşıyabilir. Exact schema henüz belirlenmez.

Human Brief, mümkün olduğunca 30–60 saniyede okunabilir; neden araştırmaya değer / değmez, ana risk, verdict ve sonraki adımı sunar. Mevcut yatırım kararı veya sahiplik ile screening sonucu ayrı tutulur.

Bu belge yalnız design kaydıdır; implementation veya gerçek screening içermez. [Open Design Questions](../architecture/open-design-questions.md) içindeki screening thresholds açık kalır.
