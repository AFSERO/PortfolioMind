# Portfolio Fit

Status: CORE DESIGN DEFINED / NOT IMPLEMENTED

## Purpose and Role

Portfolio Fit, ayrı ve lightweight bir decision-support protocol / component; lifecycle'da portfolio-context gate'tir.

> Bu asset tek başına iyi bir yatırım olsa bile mevcut portföyümüz içinde mantıklı mı?

Normal sıra Research → Valuation → Portfolio Fit → [Position Sizing](../policies/position-sizing.md) şeklindedir. Discovery / Screening'deki erken portfolio relevance kontrolünü, daha olgun research ve valuation ile değerlendirir. Business quality'yi yeniden araştırmaz. [Full Portfolio Review](full-portfolio-review.md) portföyün bütününü değerlendirirken Portfolio Fit belirli asset'in portföy içindeki uygunluğuna odaklanır.

## Inputs and Review

Compact asset research / thesis, valuation ve güncel portfolio context kullanılır. Konsept olarak:

- Current exposure
- Sector / theme overlap
- Geographic exposure
- Asset-class exposure
- Concentration
- Correlation / hidden overlap
- Portfolio role
- Liquidity
- Available capital
- Risk budget

Önerilen rolün mevcut portföye katkısı, ekleyeceği risk ve tekrar edeceği exposure açıklanır. Draft allocation target'ları binding rule değildir. Eksik look-through veya correlation verisi “overlap yok” diye yorumlanmaz; önemli context boşlukları ve freshness sınırlamaları görünür tutulur.

## Possible Results

Konsept sonuçlar: **GOOD FIT, ACCEPTABLE, POOR FIT, REVIEW REQUIRED**. Exact schema / scoring daha sonra finalize edilir.

Sonuç kısa gerekçe, ilgili constraints ve required follow-up ile birlikte sunulur. GOOD FIT / ACCEPTABLE sizing değerlendirmesine girdi olabilir; otomatik sizing run veya BUY command değildir. POOR FIT durumunda ilerlemek zorunlu değildir. Kritik bağlam eksikliği REVIEW REQUIRED olarak belirtilebilir. Bu ifadeler asset recommendation setinin yerine geçmez; buradaki REVIEW REQUIRED portfolio-fit boyutuna aittir.

## Outputs and Boundaries

Compact Machine Record konsept olarak asset / portfolio context reference, review date, role, fit result, overlap / concentration / liquidity observations, constraints, confidence ve next step taşıyabilir. Kısa Human Brief ana katkıyı, ana sorunu ve gerekli follow-up'ı özetler. Exact schema açık kalır.

Target weight veya trade execution üretmez. Fit'e ilişkin sınırlamalar Position Sizing'e aktarılır; nihai yatırım ve işlem yetkisi kullanıcıdadır. Portfolio-fit scoring ve risk-budget framework [Open Design Questions](../architecture/open-design-questions.md) içinde açık bırakılmıştır. Bu belge implementation veya gerçek yatırım analizi değildir.
