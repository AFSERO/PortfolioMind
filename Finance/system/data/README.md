# Data & External Providers — MVP Part 4B

Status: IMPLEMENTED (Part 4B: External Provider Contracts)

Dış veri kaynaklarıyla (market verisi, haber akışı, portföy durumu) iletişim kurmak üzere tasarlanmış, satıcıdan bağımsız (vendor-independent) soyut provider arayüzleri (`investment_intelligence.providers`).

## 1. Provider Kontratları

```text
MarketDataProvider
  ├── get_quote(instrument) -> MarketQuoteRecord
  └── get_price_history(instrument, *, start, end, limit) -> list[PriceBarRecord]

NewsProvider
  └── get_recent_news(instrument, *, since, until, limit) -> list[NewsItemRecord]

PortfolioProvider
  ├── get_portfolio_context() -> PortfolioSnapshotRecord
  └── get_position_context(instrument) -> PositionSnapshotRecord | None
```

## 2. Tasarım Kararları

### Sync vs Async Kararı
Mevcut persistence ve servis katmanı senkron SQLAlchemy mimarisini kullanmaktadır. Harici API'lerin ileride asenkron olabileceği varsayımıyla MVP seviyesinde tüm katmana asenkronluk karmaşıklığı (asyncio, event loop yönetimi, sync-async köprüleri) eklenmemiştir. Kontratlar **senkron** tasarlanmıştır; gelecekte spesifik bir adapter gerekirse asenkron boundary adaptör içinde izole edilecektir.

### Instrument ≠ Position Ayrımı
`Instrument` global varlık kimliğidir (`symbol`, `venue`, `currency`, `name`). `Position` ise portföydeki sahipliği ve miktarı (`quantity`, `average_cost`, `market_value`, `portfolio_weight`, `unrealized_pnl`) temsil eder. Bir enstrüman portföyde bulunmadığında `get_position_context(instrument)` hata fırlatmaz, açıkça `None` döner. NetWorth modelleri veya veritabanı tabloları bu kontratlara sızdırılmaz.

### UTC ve Freshness Semantiği
Tüm provider kayıtları (`MarketQuoteRecord.as_of`, `PriceBarRecord.timestamp`, `NewsItemRecord.published_at`, `PortfolioSnapshotRecord.as_of`) timezone-aware UTC datetime gerektirir. Naive datetime'lar reddedilir (`ValueError`); farklı timezone offset'li aware değerler otomatik olarak UTC'ye normalize edilir.

### In-Memory Test Doubles
Sözleşmelerin doğrulanması ve yerel testler için deterministik sahte sınıflar sunulmuştur:
- `StaticMarketDataProvider`
- `StaticNewsProvider`
- `StaticPortfolioProvider`
Gerçek dış API istekleri, scraping veya NetWorth entegrasyonu bu fazda yapılmamıştır.

