# Personal Investment System

Current implementation status: DESIGN / NOT IMPLEMENTED

Bu klasör gelecekteki personal investment agent architecture için ilk yapısal iskelettir. Uzun vadeli hedef, kullanıcının kısa komutlarla çalıştırabileceği, portföyünü ve yatırım fırsatlarını sürekli analiz eden kişisel AI investment system oluşturmaktır. Research, portfolio ve monitoring işlemlerinin Markdown protocol ve policy dosyaları okunarak protocol-based çalışması hedeflenmektedir.

Hedeflenen rol ayrımı: Markdown = behavior / rules / protocols / policies; Database = persistent state ve persistent source of truth; JSON = compact agent context / data interchange; detailed research = mevcut [research klasörleri](../research/README.md). Bunlar gelecek yönelimidir; mevcut context dosyalarının otoritesini değiştirmez.

CORE PROTOCOL DESIGN: MVP-READY — 15.09.2026. Core lifecycle için design freeze kaydedildi; implementation henüz yapılmadı. Bu durum bütün schema, provider, eşik ve policy sorularının çözüldüğü anlamına gelmez. Lifecycle ve rol ayrımları [System Overview](architecture/system-overview.md), kalan konular [Open Design Questions](architecture/open-design-questions.md) içindedir.

Core gate'ler: [Preliminary Screening](protocols/preliminary-screening.md) ve [Portfolio Fit](protocols/portfolio-fit.md). [Position Sizing](policies/position-sizing.md), ayrı policy / calculation component olarak tanımlıdır; high-cost AI research protocolü değildir.

Aday protocol seti: [Portfolio Monitoring](protocols/portfolio-monitoring.md), [Single Asset Monitoring](protocols/single-asset-monitoring.md), [Opportunity Discovery](protocols/opportunity-discovery.md), [Replacement Candidate](protocols/replacement-candidate.md), [Earnings Review](protocols/earnings-review.md), [Full Portfolio Review](protocols/full-portfolio-review.md), [Deep Research](protocols/deep-research.md), [Valuation Update](protocols/valuation-update.md), [Thesis Review](protocols/thesis-review.md), [News Monitoring](protocols/news-monitoring.md) ve [Technical Review](protocols/technical-review.md).
