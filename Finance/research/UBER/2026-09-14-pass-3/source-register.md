# UBER Pass 3 — Source register
**Araştırma / erişim tarihi:** 14 Eylül 2026. **Bağlı çıktılar:** [research-report.md](research-report.md), [valuation-model.md](valuation-model.md).

Bu register; tekrar kullanılan kanıtı, yeni valuation girdisini, secondary veriyi ve analist varsayımını ayırır. Fiyat snapshot'ları kaynak ekranındaki timestamp ile sabitlendi. Bilanço ve finansallar son açıklanan dönemlerine aittir; güncel fiyatla aynı tarihteymiş gibi sunulmadı.

## 1. Önceki research'ten yeniden kullanılan kaynaklar

| ID | Dosya | Kesit | Bu pass'teki rol |
|---|---|---|---|
| P1 | [Pass 1 research report](../2026-09-13-pass-1/research-report.md) | 13 Eylül 2026 | Business quality; şehir bazında density; Mobility/Delivery moat; AV MIXED; merchant/driver/provider trade-offs |
| P1-S | [Pass 1 source register](../2026-09-13-pass-1/source-register.md) | 13 Eylül 2026 | Önceden doğrulanmış primary-source attribution |
| P2 | [Pass 2 research report](../2026-09-14-pass-2/research-report.md) | 14 Eylül 2026; June financials | Financial quality, insurance, SBC, tax, capital allocation |
| P2-S | [Pass 2 source register](../2026-09-14-pass-2/source-register.md) | 14 Eylül 2026 | FY2023–25/H1 bridges, balance sheet ve 2025 normalized FCF hesabı |

P1/P2'nin business/industry araştırması baştan tekrarlanmadı. Önceden doğrulanmış financial girdilerden TTM türetildi. U02'de yalnız valuation açısından gerekli kapak/lease/investment ayrımları hedefli kontrol edildi; N04 yeni financing belgesidir. Önceki dosyalar değiştirilmedi.

### Reused primary financial references

| ID | Belge / doğrudan bağlantı | Dönem / yayın | Kullanılan içerik | Kanıt sınırı |
|---|---|---|---|---|
| U01 | [Uber 2025 10-K](https://www.sec.gov/Archives/edgar/data/1543151/000154315126000015/uber-20251231.htm) | FY2025; 13 Şubat 2026 filing | Audited financial history; SBC, OCF, tax ve leases; P2 üzerinden reuse | September bilançosu değil |
| U02 | [Uber Q2 2026 10-Q](https://www.sec.gov/Archives/edgar/data/1543151/000154315126000032/uber-20260630.htm) | 30 Haziran 2026; 5 Ağustos filing | H1 statements; cover July shares; Notes 2–5 investments/borrowing, Note 8 shares, Note 10 segments | Interim; Sept capital movements tam değil |
| U03 | [Uber FY2025 earnings](https://investor.uber.com/news-events/news/press-release-details/2026/Uber-Announces-Results-for-Fourth-Quarter-and-Full-Year-2025/) | 4 Şubat 2026 | Company FCF/Adjusted EBITDA, non-GAAP operating income ve tax bridge | Non-GAAP tanımlar ayrı tutuldu |
| U04 | [Uber Q2 2026 earnings](https://investor.uber.com/news-events/news/press-release-details/2026/Uber-Announces-Results-for-Second-Quarter-2026/default.aspx) | 5 Ağustos 2026 | H1 operating/FCF ve non-GAAP reconciliation | Company definition; owner FCF değil |
| U05 | [Uber Q2 prepared remarks](https://investor.uber.com/files/doc_earnings/2026/q2/transcript/Uber-Q2-26-Prepared-Remarks.pdf) | 5 Ağustos 2026 | Cash-tax %10–15 yakın dönem çerçevesi, SBC ve DH exposure | Management expectation; gerçekleşme/garanti değil |
| U06 | [Credit agreements 8-K](https://www.sec.gov/Archives/edgar/data/1543151/000155278126000414/e26328_uber-8k.htm) | 6 Ağustos 2026 anlaşmaları | Term/bridge/revolver; P2 reuse | Commitment drawn borrowing değildir |

Rivian/Lucid commitments, UK accounting/VAT, shareholder return ve workforce restructuring için mevcut P1/P2 primary references kullanıldı. Yeni bağımsız inceleme yapılmış gibi sunulmadı. Analyst scenario tax, reinvestment ve haircut oranları bu açıklamaların kendisi değildir.

## 2. Yeni valuation / expectations kaynakları

| ID | Kaynak | Tarih / snapshot | Kullanılan veri | Kalite / sınır |
|---|---|---|---|---|
| N01 | [Stock Analysis UBER statistics](https://stockanalysis.com/stocks/uber/statistics/) | 14 Eylül 2026, **10:06 EDT**, sayfa update 14 Eylül | **$71.62**, secondary price; $146.29B cap kontrolü | Piyasa verisi secondary; intraday; vendor EV ve net-cash çelişkisi nedeniyle alınmadı |
| N02 | [Stock Analysis UBER historical ratios](https://stockanalysis.com/stocks/uber/financials/ratios/) | 2023/24/25 year-end; erişim 14 Eylül | Market cap 126.702 / 127.016 / 169.780B | Secondary historical snapshots; continuous trading range değil |
| N03 | [Stock Analysis UBER forecast](https://stockanalysis.com/stocks/uber/forecast/) | Sayfa update 11 Eylül; erişim 14 Eylül | FY2026/FY2027 revenue 57.89/66.79B; adjusted EPS 3.36/4.41 | Consensus, company guidance değil; non-GAAP EPS |
| N04 | [Uber final eurobond prospectus 424B2](https://www.sec.gov/Archives/edgar/data/1543151/000155278126000481/e26382_uber-euro424b2.htm) | 9 Eylül dated; **11 Eylül 2026 filed** | €4.5B issue, €4.453B net proceeds, coupon, settlement, principal/cash pro forma | Primary; pricing kesinliği completion demek değil |
| N04-I | [SEC filing index](https://www.sec.gov/Archives/edgar/data/1543151/000155278126000481/0001552781-26-000481-index.html) | Filed 11 Eylül, 16:33:41 | Accession **0001552781-26-000481** ve gerçek prospectus linki | Index yalnız filing kimliği/tarihini doğrular |
| N05 | [Lyft statistics](https://stockanalysis.com/stocks/lyft/statistics/) | 14 Eylül, yaklaşık 09:51 EDT | $15.72 quote; 5.95B cap; net cash ~0.502B | Secondary, farklı timestamp/lease convention |
| N06 | [DoorDash statistics](https://stockanalysis.com/stocks/dash/statistics/) | 14 Eylül, yaklaşık 09:39 EDT | $203.18 quote; 88.04B cap; net cash ~2.04B | Vendor FCF software capex hariç; düzeltildi |
| N07 | [Airbnb statistics](https://stockanalysis.com/stocks/abnb/statistics/) | 14 Eylül, yaklaşık 09:46 EDT | $171.63 quote; 101.19B cap; net cash ~9.57B | Vendor FCF company reconciliation yerine geçmedi |

Fiyat karşılaştırmaları canlı eşzamanlı trade sinyali değildir. Peer şirketlerin current caps'i secondary sağlayıcıdan; Uber cap'i en yeni doğrulanmış actual share count ile ayrıca yeniden kuruldu. Source page'in price ve rounded ratios alanları aynı anda güncellenmeyebilir; tablodaki P/FCF'ler cap/primary FCF ile yeniden hesaplandı.

### N04 extract ve kullanım izi

- Cover: 750M euro %3.75/2029; 1B %4.125/2032; 1B %4.375/2034; 1B %4.75/2038; 750M %5.25/2046.
- Expected delivery/settlement **15 Eylül 2026**. 14 Eylül “closed financing” kabul edilmedi.
- Use of Proceeds, S-13: net proceeds yaklaşık **€4.453B**, general corporate purposes.
- Capitalization, S-14: June actual cash **4.870B**, as adjusted **10.058B**; nominal principal **12.625B → 17.868B**.
- Footnote 1 principal ile carrying amount'ı ayırır. Footnote 4 EUR/USD **1.1652**, 9 Eylül ECB oranı. Bu araştırma FX tahmini üretmez.
- N04 yeni nominal debt belirsizliğini kapatır; Pass 2'nin book-net-debt hesabını bozmaz. Net proceeds kullanılmadıkça principal-minus-cash etkisi yaklaşık 55M'dir.
- Funding için açıklanan facilities ile notes, kendiliğinden aynı anda tam drawn borrowing sayılmadı.

## 3. Yeni peer primary sources

| ID | Belge | Dönem | İncelenen kısım |
|---|---|---|---|
| L01 | [Lyft Q2 2026 results, SEC exhibit](https://investor.lyft.com/financials/sec-filings/content/0001628280-26-054305/lyft-20260630xpressrelease.htm) | Q2 / H1 2026; 6 Ağustos | Income statement, cash flows, SBC, finance lease principal, TTM company FCF reconciliation |
| D01 | [DoorDash Q2 2026 results](https://ir.doordash.com/news/news-details/2026/DoorDash-Releases-Second-Quarter-2026-Financial-Results/default.aspx) | Q2 / H1 2026 | Revenue vs Deliveroo-excluded figures; cash flows; capitalized software; TTM FCF reconciliation |
| A01 | [Airbnb Q2 2026 10-Q](https://www.sec.gov/Archives/edgar/data/1559720/000155972026000027/abnb-20260630.htm) | Q2 / H1 2026 | Income statement, SBC, FCF reconciliation; customer funds / unearned fees ve seasonality |
| A02 | [Airbnb FY2025 shareholder letter, SEC exhibit](https://www.sec.gov/Archives/edgar/data/1559720/000119312526048670/d58192dex991.htm) | Q4 / FY2025; 12 Şubat 2026 | Son bölüm FCF reconciliation, annual FCF/OCF farkı |

Peers üzerinde kapsamlı moat araştırması yapılmadı. Relative model eşlemesi ve kalite yorumu analist değerlendirmesidir. Bu pass'in asıl cash-flow normalizasyonu Uber içindir; peers'deki reported FCF'yi Uber'in fully normalized economic FCF'siyle “aynı kalite” saymadık.

### Peer calculation trace

Tutarlar B USD. Revenue/EBIT/SBC/FCF growth tabloları **H1**; price multiple denominator **TTM**.

| H1 input | Uber 2025 / 2026 | Lyft 2025 / 2026 | DoorDash 2025 / 2026 | Airbnb 2025 / 2026 |
|---|---|---|---|---|
| Revenue | 24.184 / 27.394 | 3.038355 / 3.494033 | 6.316 / 8.490 | 5.368 / 6.286 |
| 2026 GAAP operating income | 3.813 | 0.042232 | 0.307 | 0.844 |
| OCF | 4.888 / 5.213 | 0.630962 / 0.657604 | 1.139 / 1.538 | 2.764 / 2.978 |
| PP&E / scooter capex | 0.163 / 0.135 | 0.020786 / 0.050718 | 0.140 / 0.118 | 0.021 / 0.021 |
| Software capex, FCF'ye ayrıca dahil | — | — | 0.150 / 0.258 | — |
| Company FCF | 4.725 / 5.078 | 0.610176 / 0.606886 | 0.849 / 1.162 | 2.743 / 2.957 |
| 2026 SBC | 1.023 | 0.163431 | 0.580 | 0.897 |

SBC/revenue, cash-flow/statements'teki açıklanan stock compensation ile hesaplandı; capitalized SBC ve acquisition-related compensation sunumları tam standardized comp expense değildir. Cash capex dışında M&A, lease-financed varlık ve partner asset base kalır. Bu nedenle düşük cash-capex/revenue oranını tek başına düşük capital intensity saymıyoruz.

- Lyft TTM company FCF **1.1123** = 1.1951 OCF − 0.0828 capex (rounded company reconciliation). P/FCF = 5.95/1.1123 = **5.35x**.
- Lyft H1 normalized-insurance/SBC/lease basit tanısı = 0.606886 − 0.127232 − 0.163431 − 0.023147 = 0.293076B; tax ve diğer WC normalize edilmediği için full owner FCF olarak rapora taşınmadı. Headline 5.3x kalite farkını gizleyebilir.
- DoorDash TTM company FCF **2.139** = 2.830 OCF − 0.235 PP&E − 0.456 software. P/FCF = 88.04/2.139 = **41.16x**.
- DoorDash Q2 revenue +36%; Deliveroo hariç +24%. H1 headline +34.4% organic growth değildir.
- Airbnb FY2025 OCF **4.646**, capex **0.033**, FCF **4.613**. TTM FCF = 4.613 − 2.743 + 2.957 = **4.827**. P/FCF = 101.19/4.827 = **20.96x**.
- Airbnb H1 FCF yüksekliği booking timing ve unearned fees'den etkilenir. Customer funds asıl FCF'yi (bunlardan kazanılan faiz hariç) etkilemez; bunları corporate excess cash saymak uygun değildir.

## 4. UBER hesap izi ve kaynak ayrımı

### Period bridge

TTM = FY2025 − H1 2025 + H1 2026:

- GB = 193.454 − 89.574 + 111.742 = **215.622**.
- Revenue = 52.017 − 24.184 + 27.394 = **55.227**.
- EBIT = 5.565 − 2.678 + 3.813 = **6.700**.
- Adjusted EBITDA = 8.730 − 3.987 + 5.300 = **10.043**.
- Reported FCF = 9.763 − 4.725 + 5.078 = **10.116**.
- Insurance OCF = 2.660 − 1.487 + 0.830 = **2.003**.
- SBC = 1.826 − 0.910 + 1.023 = **1.939**.
- D&A = 0.747 − 0.359 + 0.386 = **0.774**.
- Finance lease principal = 0.157 − 0.075 + 0.082 = **0.164**.
- Non-insurance WC funding = 0.433 − 0.560 + 0.620 = **0.493**.

FY2025 tax-normalized cash **6.5136–6.8514**, economic **4.6876–5.0254**: Pass 2 doğrulandı. TTM cash **7.22245–7.6173**, economic **5.28345–5.6783**: bu pass'in hesabı. Modelde formül ve tüm tax girdileri vardır.

### Share count ve EV

- U02 cover: **2,042,560,121** shares outstanding at July 31, 2026. June balance adedi yerine bunu kullandık.
- U02 quarterly EPS table: Q2 diluted weighted average **2,050,225 thousand** = **2.050225B**. Bu spot fully diluted claims toplamı değildir.
- Market cap = 71.62 × 2.042560121 = **146.288155866B**.
- Borrowing net debt = 12.723 − 4.870 − 0.521 = **7.332B**.
- Conventional consolidated EV = 146.288155866 + 7.332 + 1.083 = **154.703155866B**.
- Haircut-assets sonrası operating EV = **144.703155866B**.
- Diluted proxy + operating cash buffer sonrası reverse target = 71.62 × 2.050225 + 7.332 + 1.083 + 2 − 10 = **147.2521145B**.

NCI book value ve borç carrying value, ekonomik/fair value proxy'sidir. September consolidated balance sheet bulunmadığından net capital actions için kesin pro forma uydurulmadı.

### Main cash anchor

Operating economic FCFF = 6.7×0.875 +0.774−0.308−0.164−0.493 = **5.6715B**.
Bu SBC sonrası operating cash proxy'dir; interest income ve non-operating investment kazançları dışarıda. NOL geçişi başlangıçta %12.5 cash tax, terminalde %23 tax ile senaryolaştırıldı.

## 5. Kaynakta görülen çelişkiler ve çözüm

| Konu | Gözlem | Uygulama |
|---|---|---|
| UBER vendor EV/net debt | 5.39B cash, 14.73B debt ve -4.74B net cash aynı basit tanımda uzlaşmıyor | Manual 10-Q borrowing/cash/NCI/holdings bridge |
| UBER forward P/E | Vendor 17.15x'in EPS dönemi net değil | Açık FY2026/FY2027 adjusted EPS kullanıldı |
| UBER forecast FCF serisi | Historical FY2025 tabanı 6.35B; company FCF 9.763B | Seri reverse DCF/expectations anchor'ından çıkarıldı; alternatif tanımı tahmin edilmedi |
| DoorDash FCF | Vendor ~2.60B; primary 2.139B | Software capitalization nakit harcaması düşüldü |
| Airbnb FCF | Vendor 4.860B; company 4.827B | Primary annual/H1 reconciliation kullanıldı |
| Nominal UBER debt | P2'de 25M açıklama farkı açık kalmıştı | N04 primary aggregate principal 12.625B'yi netleştirdi |
| TRS cash vs asset | 1.640B investing outflow ≠ 1.500B fair value | Holdings add-on fair value tabanı |
| Historical EV | Holdings/lease/restricted cash tanımı zaman içinde sabit değil | Güvenilir comparable EV tarihsel bandı üretilmedi; year-end P/FCF kullanıldı |

Secondary source çelişkileri hata/aldatma iddiası değildir; farklı definitions ve refresh times da neden olabilir. Tanımı uzlaştırılamayan seri modelin merkezinden çıkarıldı.

## 6. Analist varsayımları: kaynak olgusu değildir

| Varsayım | Kullanılan değer / yöntem | Dayanak ve sınır |
|---|---|---|
| Operating cash buffer | 2B | Tüm unrestricted cash'i excess saymamak; resmi minimum değil |
| Non-operating asset haircuts | Model §1; toplam 10.228B → 10B | Vergi/likidite/valuation belirsizliği; 7–12B sensitivity |
| Forecast period | Valuation tarihinden 5 rolling yıl | June TTM başlangıç proxy; calendar consensus ile birebir değil |
| Organic bookings CAGR | Bear 7.2%; Base 14.0%; Bull 18.4% | P1/P2 büyüme/moat bulgularının scenario translation'ı |
| Y5 EBIT/GB | 2.6% / 4.5% / 5.5% | SBC dahil; future contribution/operating leverage varsayımı |
| Taxes | Y1 senaryoya göre 12–15%; Y5 ve terminal 23% | U05 yakın dönem cash tax context; terminal %23 analist assumption |
| Reinvestment | Yıllık net cash allowance / bookings | Software, lease, WC, AV capital; açıklanmamış tüm guarantees'i çözmez |
| Terminal incremental ROIC | 15% / 25% / 30% | Ölçülmüş historical ROIC değil |
| Discount / terminal growth | Model §6 aralıkları | USD nominal hurdle; kesin CAPM WACC değil |
| Share count | Sabit 2.050225B proxy | SBC cash-equivalent maliyeti EBIT'te; buyback upside double count edilmez |
| M&A incremental NPV | Merkez 0; stress -5/+3B | Closing synergy/valuation tahmini değil; perimeter discipline |
| AV stress | Growth, margin, reinvestment ve ROIC farkları | Contract economics açıklanmadığından örnek sensitivity |
| Invalidation triggers | Rapor §12 | Araştırma eşikleri; şirket guidance/covenant değil |
| WATCHLIST price ranges | $50–55 / conditional $55–60 | DCF base'e discount; price trigger tek başına conclusion değiştirmez |

## 7. Kalan belirsizlikler ve durdurma

Kararı en çok etkileyen belirsizlikler; net insurance cash economics, normalized owner cash, future margin/reinvestment ve DH/AV capital discipline'dır. Public disclosures, özellikle commercial AV contribution ve bütün claims/receivables köprüsü için kesin yanıt sağlamıyor.

Daha güncel earnings dönemi yokken tahmini bilanço; private holdings için sahte live marks; peers için yüzeysel “tam normalized FCF”; veya tek kesin terminal multiple üretilmedi. Bu sınırlar final **WATCHLIST / MEDIUM** conclusion'ında zaten karşılığını buluyor. Fundamental araştırma bu pass ile tamamlandı.

## 8. Dosya bütünlüğü

Önceki dosyalar için çalışma sırasında kaydedilen SHA-256 değerleri:

| Dosya | SHA-256 |
|---|---|
| Pass 1 README | D6BF50BCAF4202EEB4943EEC7ABCE6D4AA885F56053A89044E0B65A65C03F277 |
| Pass 1 research-report | 69FF8B69DCB073928B591877DEEB7F2ECABA21A795CE29A65BC2A97F91E035FA |
| Pass 1 source-register | 990AC55FD67D44206379BEDABE7D1C2B968672734E78E9973945938E2066099B |
| Pass 2 research-report | 288887329918CF7E5485D6EC22E309DE2B1EDFCEC877528790137D85C5359CC0 |
| Pass 2 source-register | 3464D7C3CAB3380299FB2E07365E1B941FE91DB1620F0BE94F11F06027D183E9 |

