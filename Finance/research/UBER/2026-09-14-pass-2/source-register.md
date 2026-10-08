# UBER Pass 2 — Source register ve hesaplama izi

**Araştırma tarihi:** 14 Eylül 2026. **Bağlı çıktı:** [research-report.md](research-report.md). **Kapsam:** financial quality, cash flow, SBC, insurance, tax, balance sheet ve capital allocation. Valuation yapılmamıştır.

Finansal gerçekleşme kesiti 30 Haziran 2026'dır. Sonraki olaylar kendi tarihleriyle tutulmuştur. Primary sources kullanıldı; material hesapları desteklemek için secondary finansal veri sağlayıcısı, sosyal medya veya AI özeti kullanılmadı. Kaynaklar çevrimiçi incelendi; bu klasör ham SEC dosyalarının arşivi değildir.

## 1. Kaynak envanteri

| ID | Primary source | Dönem / tarih | Kullanılan bölüm ve işlev | Sınır |
|---|---|---|---|---|
| S01 | [Uber 2025 Form 10-K](https://www.sec.gov/Archives/edgar/data/1543151/000154315126000015/uber-20251231.htm) | 31 Aralık 2025; 13 Şubat 2026 filing | Financial statements; MD&A quarterly metrics, operating expenses; Note 1 accounting/insurance/VAT/Foodpanda; Notes 2, 8–13; Schedule II | 2023–2025 audited geçmiş; Haziran/Eylül mevcut durumunun yerine geçmez. |
| S02 | [Uber 2026 Q2 Form 10-Q](https://www.sec.gov/Archives/edgar/data/1543151/000154315126000032/uber-20260630.htm) | 30 Haziran 2026; 5 Ağustos 2026 filing | H1 financial statements; Notes 2–5 investments/debt, Note 8 equity, Note 10 segments; MD&A; subsequent events | Interim statements; H1, yıllık değil. Insurance full payout triangle yok. |
| S03 | [Uber 2024 Form 10-K](https://www.sec.gov/Archives/edgar/data/1543151/000154315125000008/uber-20241231.htm) | 31 Aralık 2024; 14 Şubat 2025 filing | 2022 karşılaştırmalı mali tablolar, EPS/SBC; 2023–2024 quarterly bookings; 2024 insurance cost açıklaması | Tarihsel kaynak; güncel finansman için kullanılmadı. |
| S04 | [FY2023 earnings release](https://investor.uber.com/news-events/news/press-release-details/2024/Uber-Announces-Results-for-Fourth-Quarter-and-Full-Year-2023/default.aspx) | 7 Şubat 2024 | FY2022/2023 GB, EBITDA, OCF/FCF; annual highlights | Company-defined non-GAAP ölçüler, GAAP mutabakatlarıyla kullanıldı. |
| S05 | [FY2024 earnings release](https://investor.uber.com/news-events/news/press-release-details/2025/Uber-Announces-Results-for-Fourth-Quarter-and-Full-Year-2024/default.aspx) | 5 Şubat 2025 | FY2024 financial highlights, FCF ve tax benefit kontrolü | S01/S03 tarihsel rakamlarıyla çapraz kontrol. |
| S06 | [FY2025 earnings release](https://investor.uber.com/news-events/news/press-release-details/2026/Uber-Announces-Results-for-Fourth-Quarter-and-Full-Year-2025/) | 4 Şubat 2026 | Annual highlights; non-GAAP operating income 6,453; tax benefit; FCF reconciliation | $5 milyar tax benefit, cash income tax değildir. |
| S07 | [Q2 2026 earnings release](https://investor.uber.com/news-events/news/press-release-details/2026/Uber-Announces-Results-for-Second-Quarter-2026/default.aspx) | 5 Ağustos 2026 | Q2 EBITDA 2,819; H1 finansallar, non-GAAP reconciliation | Segment definition değişimi ayrı takip edildi. |
| S08 | [Q1 2026 earnings release](https://investor.uber.com/news-events/news/press-release-details/2026/Uber-Announces-Results-for-First-Quarter-2026/default.aspx) | Q1 2026 sonuçları | Q1 EBITDA 2,481; H1 toplamının kurulması; quarterly bookings | H1 tek çeyrekten yıllıklaştırılmadı. |
| S09 | [Q2 2026 prepared remarks](https://investor.uber.com/files/doc_earnings/2026/q2/transcript/Uber-Q2-26-Prepared-Remarks.pdf) | 5 Ağustos 2026, 9 sayfa | PDF s.7–9: TTM FCF, capital allocation, Delivery Hero exposure, SBC/cash tax guidance; dipnot 1 tax denominator | Yönetim beyanı/beklenti; bağımsız garanti veya gerçekleşme değil. |
| S10 | [Credit agreements Form 8-K](https://www.sec.gov/Archives/edgar/data/1543151/000155278126000414/e26328_uber-8k.htm) | 6 Ağustos 2026 anlaşmaları | €4 milyar term facility, bridge reduction, $7,7 milyar revolver ve vadeler | Commitment ile drawn debt ayrıldı. |
| S11 | [Preliminary prospectus supplement](https://www.sec.gov/Archives/edgar/data/1543151/000155278126000469/e26355_uber-euro424b3.htm) | 7 Eylül 2026 | Yeni finansman süreci, existing credit arrangements | İncelenen metinde nihai issue amount/coupon eksik; tamamlanmış ihraç varsayılmadı. |
| S12 | [Building a simpler, faster Uber](https://www.uber.com/ca/en/newsroom/simplerfasteruber/) | 2 Eylül 2026 | CEO açıklaması: yaklaşık %10 workforce azaltımı, savings reinvestment | Cash restructuring charge tutarı verilmemiş. |
| S13 | [Uber–Rivian agreement announcement](https://investor.uber.com/news-events/news/press-release-details/2026/Uber-and-Rivian-Partner-to-Deploy-up-to-50000-Fully-Autonomous-Robotaxis-2026-TViR4R05gi/default.aspx) | 19 Mart 2026 | $1,25 milyara kadar milestone investment; initial $300 milyon; araç alımlarında Uber/fleet partner ayrımı | Tam ticari sözleşme değil; opsiyonlar kesin borç sayılmadı. |
| S14 | [Lucid investment / robotaxi expansion](https://ir.lucidmotors.com/news-releases/news-release-details/lucid-receive-new-investments-pif-and-uber-uber-and-lucid-expand) | 14 Nisan 2026 | Ek $200 milyon / toplam $500 milyon yatırım; en az 35 bin araç purchase commitment | Investment commitment ile gerçekleşen harcama/araç financing aynı değil. |

Tüm kaynaklara bu araştırma kapsamında 14 Eylül 2026 erişildi. S01/S03 audited financial statements ile S02 interim tabloları en yüksek ağırlıkta kullanıldı. Basın açıklaması, SEC filing'le uyuşmayan bir tanıma zorla dönüştürülmedi. S09'un forward-looking tax/capital allocation beyanları raporda açıkça yönetim beklentisi olarak etiketlendi.

## 2. Ölçüm ve kanıt kuralları

- Tutarlar milyon USD; hisseler milyon adet; EPS ve per-share USD. SEC'in bin adet verdiği hisse verileri 1,000'e bölündü.
- Net income trend tablosu Uber'e atfedilen kârdır. OCF köprüsü NCI dahil konsolide net income ile başlar.
- FCF, OCF eksi cash PP&E purchases. Finance lease principal, investing/acquisition ve buybacks company FCF dışında kalır.
- H1 = ilk altı ay. TTM = FY2025 − H1 2025 + H1 2026. H1 rakamları ikiyle çarpılıp yıllık tahmin yapılmadı.
- “WC” cash flow tablosundaki işletme varlık/yükümlülük değişimlerinin tamamı için kullanılan geniş kısaltmadır; bilanço current assets-current liabilities ölçüsü değildir.
- 2023–2025 segment EBITDA, 2026 Segment Operating Income ile tek seri yapılmadı. H1 2025/26 yeni tanım karşılaştırması kullanıldı.
- Raporun normalizasyonları **araştırmacı hesabı**; company guidance veya audited alternatif FCF değildir.
- 2025/H1 2026 bilanço değerleri Eylül fiyatına taşınmadı. Offer price ve convertible sözleşme fiyatı açıklanan şartlardır; bu araştırmanın hisse fair value tahmini değildir.

## 3. Historical veri ve FCF mutabakatı

| Dönem | GB | Revenue | Op income | Adj EBITDA | OCF | Cash capex | FCF | Net income Uber | Diluted EPS | Ana kaynak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2022 | 115395 | 31877 | -1832 | 1713 | 642 | 252 | 390 | -9141 | -4.65 | S03/S04 |
| 2023 | 137865 | 37281 | 1110 | 4052 | 3585 | 223 | 3362 | 1887 | .87 | S01/S04 |
| 2024 | 162773 | 43978 | 2799 | 6484 | 7137 | 242 | 6895 | 9856 | 4.56 | S01/S05 |
| 2025 | 193454 | 52017 | 5565 | 8730 | 10099 | 336 | 9763 | 10053 | 4.73 | S01/S06 |
| H1 2025 | 89574 | 24184 | 2678 | 3987 | 4888 | 163 | 4725 | 3131 | 1.46 | S02/S07/S08 |
| H1 2026 | 111742 | 27394 | 3813 | 5300 | 5213 | 135 | 5078 | 2657 | 1.29 | S02/S07/S08 |

Her sütunda `OCF − capex = FCF` kontrol edildi. H1 EBITDA: 2025 `1868 + 2119 = 3987`; 2026 `2481 + 2819 = 5300`. H1 GB: 2025 `42818 + 46756 = 89574`; 2026 `53720 + 58022 = 111742`. TTM reported FCF `9763 − 4725 + 5078 = 10116`.

### Net income'dan OCF'ye tam satır izi

S01, Consolidated Statements of Cash Flows, basılı s.78–79; S02, Condensed Consolidated Statements of Cash Flows. Nakit kullanımına eksi işareti verildi.

| Cash flow reconciliation satırı | 2023 | 2024 | 2025 | H1 2025 | H1 2026 |
|---|---:|---:|---:|---:|---:|
| Net income including NCI | 2156 | 9845 | 10093 | 3124 | 2698 |
| Depreciation/amortization | 823 | 737 | 747 | 359 | 386 |
| SBC | 1935 | 1796 | 1826 | 910 | 1023 |
| Deferred income taxes | 26 | -6027 | -4779 | -325 | 771 |
| Accretion of discounts on marketable debt, net | -154 | -251 | -158 | ayrı satır yok | ayrı satır yok |
| Unrealized gain/loss on debt/equity | -1610 | -1832 | 97 | -34 | -138 |
| Unrealized FX | 138 | 308 | -120 | -152 | -53 |
| Other reconciliation | 106 | 187 | 166 | 79 | 316 |
| **Varlık/yükümlülük değişimleri öncesi toplam** | **3420** | **4763** | **7872** | **3961** | **5003** |
| Accounts receivable | -758 | -142 | -466 | -335 | -499 |
| Prepaid expenses and other assets | -1462 | -694 | -1028 | -748 | -375 |
| Operating lease ROU assets | 191 | 196 | 177 | 89 | 100 |
| Accounts payable | 64 | 86 | 126 | 131 | 345 |
| Accrued insurance reserves | 2230 | 2819 | 2660 | 1487 | 830 |
| Accrued expenses and other liabilities | 80 | 330 | 967 | 410 | -94 |
| Operating lease liabilities | -180 | -221 | -209 | -107 | -97 |
| **Toplam asset/liability change** | **165** | **2374** | **2227** | **927** | **210** |
| **OCF** | **3585** | **7137** | **10099** | **4888** | **5213** |

H1'de ayrı accretion satırı bulunmaması sıfır ekonomik accretion anlamına gelmez; filing'in kendi toplulaştırılmış other satırı aynen korunmuştur. Rapordaki “diğer non-cash / reconciliation” = D&A + deferred tax + accretion + investment adjustment + FX + other; SBC bu toplamın dışındadır. Bu tutarlar sırasıyla -671, -6878, -4047, -73, 1282'dir.

Tam köprü örnekleri:

`2025 OCF = 10093 + 747 + 1826 − 4779 − 158 + 97 − 120 + 166 − 466 − 1028 + 177 + 126 + 2660 + 967 − 209 = 10099`.

`H1 2026 OCF = 2698 + 386 + 1023 + 771 − 138 − 53 + 316 − 499 − 375 + 100 + 345 + 830 − 94 − 97 = 5213`.

`Insurance hariç WC = toplam asset/liability change − insurance satırı`: -2065 / -445 / -433 / -560 / -620.

`2025 FCF artışı = 9763 − 6895 = 2868`; `insurance katkısı değişimi = 2660 − 2819 = −159`.

`H1 FCF artışı = 5078 − 4725 = 353`; `WC desteği değişimi = 210 − 927 = −717`; `WC öncesi FCF artışı = 353 + 717 = 1070`.

## 4. Segment calculations

S03 ve S01 MD&A quarterly key metrics tablolarından bookings toplamları:

| Segment / yıl | Q1 | Q2 | Q3 | Q4 | Yıllık toplam |
|---|---:|---:|---:|---:|---:|
| Mobility 2023 | 14981 | 16728 | 17903 | 19285 | 68897 |
| Delivery 2023 | 15026 | 15595 | 16094 | 17011 | 63726 |
| Freight 2023 | 1401 | 1278 | 1284 | 1279 | 5242 |
| Mobility 2024 | 18670 | 20554 | 21002 | 22798 | 83024 |
| Delivery 2024 | 17699 | 18126 | 18663 | 20126 | 74614 |
| Freight 2024 | 1282 | 1272 | 1308 | 1273 | 5135 |
| Mobility 2025 | 21182 | 23762 | 25111 | 27442 | 97497 |
| Delivery 2025 | 20377 | 21734 | 23322 | 25431 | 90864 |
| Freight 2025 | 1259 | 1260 | 1307 | 1267 | 5093 |

Kontroller: `68897+63726+5242=137865`; `83024+74614+5135=162773`; `97497+90864+5093=193454`.

S01 Note 13 annual segment revenue / EBITDA:

| Segment | Revenue 2023 / 2024 / 2025 | EBITDA 2023 / 2024 / 2025 |
|---|---|---|
| Mobility | 19832 / 25087 / 29670 | 4963 / 6497 / 7899 |
| Delivery | 12204 / 13750 / 17248 | 1506 / 2471 / 3572 |
| Freight | 5245 / 5141 / 5099 | -64 / -74 / -33 |
| Unallocated corporate costs | uygulanmaz | 2353 / 2410 / 2708, toplamdan çıkarılır |

Consolidated EBITDA kontrolleri: `4963+1506−64−2353=4052`; `6497+2471−74−2410=6484`; `7899+3572−33−2708=8730`.

Marjlar: `segment kâr / aynı dönem segment bookings ×100` veya açıkça etiketlenmişse `/ segment revenue`. Incremental: `(kâr_t − kâr_t−1)/(bookings_t − bookings_t−1)`.

| Incremental hesap | Sonuç |
|---|---:|
| Mobility 2024: (6497−4963)/(83024−68897) | 10.8586% |
| Mobility 2025: (7899−6497)/(97497−83024) | 9.6870% |
| Delivery 2024: (2471−1506)/(74614−63726) | 8.8630% |
| Delivery 2025: (3572−2471)/(90864−74614) | 6.7754% |
| Mobility H1 2026: (4244−3316)/(55382−44944), yeni SOI | 8.8906% |
| Delivery H1 2026: (2016−1437)/(53455−42111), yeni SOI | 5.1040% |

S02 Note 10 H1 yeni ölçü girdileri:

| Segment | GB H1 2025 / 2026 | Revenue H1 2025 / 2026 | SOI H1 2025 / 2026 |
|---|---|---|---|
| Mobility | 44944 / 55382 | 13784 / 14161 | 3316 / 4244 |
| Delivery | 42111 / 53455 | 7879 / 10313 | 1437 / 2016 |
| Freight | 2519 / 2905 | 2521 / 2920 | -51 / -54 |
| Unallocated corporate | — | — | 1842 / 2180, toplamdan çıkarılır |

Yeni tanım mutabakatı: H1 2025 `3316+1437−51−1842=2860` non-GAAP operating income; `2860−182=2678` GAAP. H1 2026 `4244+2016−54−2180=4026`; `4026−213=3813`. Corporate costs hariç segment marjı, Uber hissedarına kalan nihai marj değildir.

## 5. SBC ve pay başına hesaplar

Kaynaklar S03 financial statements/EPS; S01 Notes 10/12 ve equity/cash flows; S02 equity/EPS/Note 8.

| Dönem | SBC | Basic weighted-average, milyon | Diluted weighted-average, milyon |
|---|---:|---:|---:|
| 2022 | 1793 | 1972.131 | 1974.928 |
| 2023 | 1935 | 2035.651 | 2091.782 |
| 2024 | 1796 | 2094.602 | 2150.508 |
| 2025 | 1826 | 2085.253 | 2119.689 |
| H1 2025 | 910 | 2091.781 | 2124.181 |
| H1 2026 | 1023 | 2044.279 | 2060.763 |

Formüller: `SBC/revenue`, `SBC/FCF`, `FCF/diluted weighted-average shares`, `GAAP operating income/diluted weighted-average shares`. SBC-adjusted per share yalnızca `(FCF−SBC)/aynı payda` proxy'sidir.

Örnekler:

- 2025 FCF/share = `9763/2119.689 = 4.6059`; 2025 op income/share = `5565/2119.689 = 2.6254`.
- H1 FCF/share artışı = `(5078/2060.763)/(4725/2124.181)−1 = 10.7782%`.
- H1 op income/share artışı = `(3813/2060.763)/(2678/2124.181)−1 = 46.7641%`.
- H1 toplam FCF artışı = `5078/4725−1 = 7.4709%`; operating income artışı = `3813/2678−1 = 42.3824%`.
- 2025 buyback/FCF = `6523/9763 = 66.8135%`; H1 2026 = `3529/5078 = 69.4959%`.

2025 common shares issued/outstanding köprüsü, milyon:

`2107.953 + 1.523 option exercise + 35.392 RSU vesting + 3.098 ESPP − .659 tax withholding + .576 convertible settlement − 79.978 repurchased = 2067.905`.

`Net issuance = 39.930`; `net count change = −40.048`; `39.930/79.978 ≈ 49.9%`. Bu bir **hisse adedi offset** hesabı; SBC yerine geçen kesin nakit maliyeti değil. 2025 equity repurchase tutarı 6,560 iken cash flow satırı 6,523; muhasebe/nakit kapsamı farklı olduğundan eşitlenmedi.

H1 2026 dönem sonu count değişimi: `2039.994−2067.905=−27.911` milyon; `−27.911/2067.905≈−1.35%`. Yaklaşık 46.6 milyon repurchase'a karşılık kalan net ihraç yaklaşık 18.7 milyon. H1 weighted-average diluted düşüşü yaklaşık %2.99; dönem sonu düşüşünden farklıdır.

RSU kontrolü, S02 Note 8: `57.654 unvested başlangıç + 35.921 granted − 17.008 vested − 4.763 cancelled = 71.804 unvested bitiş`. Bu RSU hareketi bütün ortak hisse hareketini temsil etmez. Unrecognized compensation: yaklaşık 3,500 → 4,900; remaining recognition period 2.64 → 2.93 yıl.

EPS şirketten aynen alındı: diluted numerator Freight Holding contingent-share gibi düzeltmeler içerebilir. Net income ile diluted share sayısını bölerek bulunan fark yanlış veri diye düzeltilmedi. SBC'yi ve antidilution buyback'i aynı ekonomik hesapta iki kez düşmedik.

## 6. Insurance kanıt zinciri

S01 Schedule II reserve roll-forward:

`2023: 4754 + 3544 − 1526 + 214 = 6986`.

`2024: 6986 + 4489 − 1696 + 17 = 9796`.

`2025: 9796 + 4879 − 2421 + 209 = 12463`.

Önceki yıllar claims revision, adverse pozitif: `2023 +158; 2024 −78; 2025 −21`. 2025 favorable revision/operating income = `21/5565 = .3774%`.

Other sütunu karşılık gelen recoverable ile rezerv değişimini içerir. S01'de karşılık gelen recoverable ile ilişkili insurance reserves 2024/2025 için 264/473. Bu nedenle reserve roll-forward, net premium/paid claims cash flow hesabıyla aynı değildir. Deductions 2,421'i bütün insurance cash expense, additions 4,879'u bütün insurance expense olarak kullanmadık.

Bilanço rezerv değişimi ve OCF satırı eşit olmak zorunda değildir: `12463−9796=2667`, OCF katkısı `2660`. H1'de `3758+9528=13286`; `13286−12463=823`, OCF satırı `830`. Kaynak S01/S02. Bu küçük farkları düzeltilmemiş bir tablo hatası saymadık; cash flow hareketleri acquisition/disposal ve diğer bilanço etkilerinden arındırılmış kapsam taşır.

Insurance maliyet **artışı** için S01 MD&A 851 milyon; S03 MD&A yaklaşık 1.3 milyar. Bunlar mil başına fiyat ile hacim etkisini birlikte içerir. Claims inflation'a özel saf zaman serisi açıklanmamıştır.

Restricted asset hesapları, S01/S02 balance sheet ve investment notes:

| Dönem | Current restricted cash | Non-current restricted cash | Restricted investments | Toplam |
|---|---:|---:|---:|---:|
| 2024 sonu | 545 | 2172 | 7019 | 9736 |
| 2025 sonu | 631 | 1911 | 8874 | 11416 |
| Haziran 2026 | 661 | 1646 | 9486 | 11793 |

Stok artışları 1,680 ve 377'dir. Bu artışlar **nakit bağlanmasının kesin flow ölçüsü olarak kullanılmadı**. Kısıtlamalar tümüyle insurance değildir; fair value/FX/reclassification etkileri vardır. Normalizasyon formülüne insurance OCF katkısı yanında yeniden konmadı.

Kamuya açık kanıt sınırı: incelenen filings, bütün insurance premiums, paid claims, captive transfers, third-party recoveries ve accident-year development için tek bir net nakit köprüsü vermiyor. Eksik ayrıntı var diye rezerv manipulation sonucu üretilmedi; favorable development küçük diye yeterlilik kesinleşmiş sayılmadı.

## 7. Incentives ve working capital kanıtı

S01 Note 1, Revenue Recognition / Incentives to Customers / End-User Discounts and Promotions: ayrı mal veya hizmet alınmayan customer incentives revenue reduction; referral distinct service ve non-customer targeted promotions çoğunlukla sales & marketing; market-wide promosyonlar revenue reduction. Principal/agent değerlendirmesi sunumu değiştirir. Bu nedenle farklı satırlardan eksik teşvik rakamlarını toplayıp global subsidy oluşturmadık.

S01 MD&A: consumer discounts/promotions/credits/refunds 2025 yaklaşık 1.6 milyar, 2024 yaklaşık 1.4 milyar; açıklanan artış 207. Yuvarlak milyar değerlerinden 200 hesaplayıp 207'yi değiştirmedik. S02 MD&A H1 courier payments/incentives artışı yaklaşık 1.2 milyar; driver payments/incentives düşüşü yaklaşık 1.4 milyar ve UK model değişimiyle bağlantılı. Bunlar saf incremental subsidy değil.

S01 Note 9: accrued Drivers and Merchants liability 2024/2025 `1421/1626`; artış `205`. Bu bilanço hareketini doğrudan OCF'nin accrued other liabilities satırına eşitlemedik. S01 Note 1 Freight: brokerage payment terms genellikle 30–45 gün; transportation management 30–60 gün; taşıyıcıya ödeme yükümlülüğü shipper tahsilatından bağımsız olabilir. Tüm grubun settlement günleri için yeterli ayrıştırma yok.

## 8. Balance sheet ve investments izi

S02 balance sheet / Note 5:

`2025 serbest likidite = 7105+528=7633`; `net debt =10521−7633=2888`.

`Haziran 2026 serbest likidite =4870+521=5391`; `net debt =12723−5391=7332`.

Book debt = `2000+1725+1324+1500+1250+1000+1500+1250+1250−76=12723`. **Nominal borç açıklama farkı:** S01 future minimum principal toplamı 10600 ve 2028 ödemesi2850; convertible1725 çıkarılınca exchangeable için1125 ima ediliyor. Ancak S01/S02 exchangeable issuance açıklaması1150 veriyor. 25 milyonluk farkı doğrulayacak bir principal retirement köprüsü bu incelemede belirlenmedi. 2025 fair-value carrying1125'i otomatik nominal principal saymadık. Bu nedenle 2026 nominal toplamını kesin12600 olarak raporlamadık; net debt için doğrulanmış book12723 kullanıldı. Book/fair/nominal debt birbirine eşit değildir ve bu küçük açıklama farkı kaynak belirsizliği olarak korunmuştur.

Interest expense 2023/24/25: `633/523/440`; interest income `484/721/743`, S01 statements. H1 2026 expense/income `235/347`, S02. Coverage `3813/235=16.2255x`; kredi sözleşmesinin covenant tanımı değildir. Operating lease liabilities 2025/June2026 `1559/2008`, net debt'in dışında açıkça gösterildi.

S10/S11 financing: bridge başlangıç `€14.2bn`; yeni term `€4.0bn`; kalan bridge `€10.2bn`. Facility alternatives/commitment reduction nedeniyle toplam ilave financing kapasitesi diye `14.2+4.0` hesaplanmadı. Yeni revolver `USD7.7bn`, eski `USD5.0bn` yerine. Başlangıçtaki June term facility'de undrawn `USD1bn` için 2 Ağustos expiry bilgisi var; Eylül cash capacity'ye otomatik taşınmadı. Final Eylül bond pricing/completion bu kaynak setinde doğrulanmadı; tahmini borç kaydı yok.

S02 Note 2 holdings:

| Holding | 2025 | Haziran 2026 |
|---|---:|---:|
| Didi | 3011 | 1900 |
| Other non-marketable | 1455 | 2263 |
| Grab | 2674 | 2020 |
| Aurora | 1252 | 1763 |
| Other marketable | 667 | 813 |
| Bu securities tablosundaki note receivable | 119 | 0 |
| **Toplam** | **9178** | **8759** |

S02 Note 3 equity method: `Delivery Hero3502 + Careem147 + other124 =3773`; `8759+3773=12532`. 2025 eşdeğer toplam `9178+287=9465`. Loan/convertible receivable ve türevler başka bilanço satırlarında da bulunabilir; burada tüm yatırımların tam likidasyon değerine ulaşıldığı iddia edilmiyor.

Delivery Hero: doğrudan pay %24.99 (S02 Note 3); türevler dahil yaklaşık %37 ekonomik interest (S09). Haziran carrying3502/fair3100. Prior fair-value remeasurement, equity-method'e geçiş öncesinde gerçekleşir; operasyonel kâr değildir. Careem yaklaşık %45 Haziran; 30 Temmuz control acquisition sonrası yeniden konsolidasyon olayı ayrı kaydedildi.

## 9. Capital allocation cash-flow sınırları

S01/S02 cash flow tabloları temel alınır. Sayılar bazı yerde net issuance fees, bazı yerde gross principal olduğu için issuance−repayment doğrudan book debt değişimi değildir. Exchangeable fair value ve fees de book debt'i etkiler.

| Cash flow | 2023 | 2024 | 2025 | H1 2026 |
|---|---:|---:|---:|---:|
| Net cash used in investing | -3226 | -3177 | -3564 | -6162 |
| Purchases of non-marketable equity | -52 | -289 | -676 | -507 |
| Purchases of marketable securities | -8774 | -12765 | -21447 | -17646 |
| Marketable maturities/sales | 5069 | 10204 | 20046 | 14665 |
| Sales of equity-method investments | 721 | 17 | 0 | ayrı satır yok |
| Business acquisitions, net cash acquired | 0 | 0 | -815 | -653 |
| Notes receivable cash outflow, ayrı H1 satırı | ayrı satır yok | ayrı satır yok | ayrı satır yok | -298 |
| Total return swaps, ayrı H1 satırı | ayrı satır yok | ayrı satır yok | ayrı satır yok | -1640 |
| Other investing | 33 | -102 | -336 | 52 |
| Cash PP&E purchases | -223 | -242 | -336 | -135 |

2023/24/25 investing toplamları satırlardan yeniden hesaplanabilir. H1'de de `−507−17646+14665−653−298−1640+52−135=−6162`. Securities purchases içinde treasury/restricted yatırım yönetimi ile strategic marketable holdings olabilir; hepsi M&A harcaması sayılmadı.

Financing seçili kalemleri: 2025 issuance3359, repayment2350, lease principal157, ESPP183, buyback6523, NCI109, other−116; net financing `−5713`. H1 2026 issuance3997, repayment2000, lease82, ESPP136, buyback3529, other−73; net financing `−1551`. Buyback cash kullanımı, OCF'nin elde edilme maliyeti değildir.

S13/S14'te açıklanan AV yatırım ve purchase commitment tutarları bu tarihsel cash flows'a yeniden nakit ödeme olarak eklenmedi: gerçekleşme tarihi, fleet partner payı ve milestone koşulları tam eşleşmiyor. Lucid ek200/toplam500, Rivian en fazla1250 ve initial300 birbiriyle farklı anlaşmalardır. Araç adedi × varsayımsal araç fiyatı kullanılarak borç üretilmedi.

## 10. Tax ve özel nakit kalemleri

S01 Note 11, cash flow supplementary disclosures; S02 income tax/cash flows:

| Gösterge | 2023 | 2024 | 2025 | H1 2025 | H1 2026 |
|---|---:|---:|---:|---:|---:|
| Income tax expense (+) / benefit (−) | 213 | -5758 | -4346 | -260 | 1034 |
| Cash income tax, net refunds | 234 | 324 | 345 | 167 | 280 |

2025 cash tax split, S01: federal12+state81+foreign252=345. Non-income VAT ödemeleri bu sütuna eklenmemiştir. 2024 US tax valuation release yaklaşık6400; 2025 Netherlands release5000. Deferred tax noncash adjustments OCF'de zaten var.

Cash tax sensitivity, S09 dipnot1:

`Tax base proxy = non-GAAP operating income − interest expense + interest income`.

2025: `6453−440+743=6756`; `6756×10%=675.6`; `6756×15%=1013.4`; gerçek345 üstünde **330.6–668.4**. Earnings girdileri S06/S01.

H1 2026: `4026−235+347=4138`; `4138×10%=413.8`; `4138×15%=620.7`; gerçek280 üstünde **133.8–340.7**. Earnings girdileri S02/S07.

Bu, ileri dönem yönetim cash-tax bandını eski earnings tabanına uygulayan karşılaştırmadır. Non-GAAP ETR %22–24 ayrı kavramdır. Tax law/NOL tüketimi tam modellenmedi. Gelecek faaliyet kârı veya tax rate tahmini yapılmadı.

S01 Note 11 net DTA2024/25 `6163/10923`; balance sheet DTA2025 `10951`; netting/presentation ayrımı korunur. Federal NOL finite yaklaşık43, indefinite yaklaşık4100; state7000, foreign20300. Bunlar tax loss miktarları, doğrudan tax credit/cash değil.

Foodpanda: S01 Note1/other income expense açıklaması, expense236 2024; Nisan2025 cash payment236. Yalnızca 2025 normalizasyonuna +236 eklendi. UK VAT: S01 contingencies, 2023–2025 cumulative payment yaklaşık1800 ve asset recognition. Bu tutar FCF'ye geri eklenmedi; iade/claim sonucu kesin değil. S12 restructuring duyurusunda toplam cash charge açıklanmadığından sayısal add-back yapılmadı.

## 11. Normalizasyon formülü ve alternatif kontroller

### Dar duyarlılık senaryosu: yeni insurance float katkısı yok, cash tax %10–15

`Normalized cash FCF = reported FCF − insurance OCF contribution − finance lease principal + açık non-recurring cash add-back − incremental cash tax`.

`Shareholder economic proxy = normalized cash FCF − GAAP SBC expense`.

| İşlem | 2025 | H1 2026 |
|---|---:|---:|
| Reported FCF | 9763 | 5078 |
| Insurance katkısı çıkar | -2660 | -830 |
| Finance lease principal çıkar | -157 | -82 |
| Foodpanda cash add-back | +236 | 0 |
| Tax öncesi düzeltilmiş taban | 7182 | 4166 |
| Incremental tax düşük / yüksek | 330.6 / 668.4 | 133.8 / 340.7 |
| Normalized cash, düşük–yüksek | **6513.6–6851.4** | **3825.3–4032.2** |
| SBC | -1826 | -1023 |
| Shareholder economic proxy, düşük–yüksek | **4687.6–5025.4** | **2802.3–3009.2** |

Sunumda büyüklükler yaklaşık `2025: $6.5–6.9bn / $4.7–5.0bn`; `H1 2026: $3.8–4.0bn / $2.8–3.0bn`. Bu dar bandın bütün belirsizliği kapsamadığı raporda açıkça belirtilmiştir. İki dönem farklı özel nakit/WC koşulları taşır; yalnızca aralık farkını organik normalized büyüme saymadık.

Tanısal alternatifler:

| Hesap | 2023 | 2024 | 2025 | H1 2025 | H1 2026 |
|---|---:|---:|---:|---:|---:|
| FCF−SBC | 1427 | 5099 | 7937 | 3815 | 4055 |
| FCF−insuranceOCF−SBC | -803 | 2280 | 5277 | 2328 | 3225 |
| FCF−totalWC−SBC | 1262 | 2725 | 5710 | 2888 | 3845 |

Son iki satır birlikte uygulanmaz. Total WC zaten insurance'ı içerir. Diğer kontrol: 2025 `FCF−insurance=7103`, SBC dahil değildir; `FCF−SBC=7937`, insurance hariç değildir. Farklı tanımlar tek normalized rakam gibi kullanılmadı.

### Dahil edilmeyen / çifte sayımı engellenen kalemler

| Kalem | İşlem | Neden |
|---|---|---|
| Restricted asset stok artışı | Ayrıca düşülmedi | Rezerv funding ile çakışabilir; stok değişimi saf cash flow değil. |
| DTA allowance release | FCF'den tekrar düşülmedi | OCF'deki deferred tax reconciliation zaten ters çeviriyor. |
| Noncash equity gain/loss | FCF'ye tekrar eklenip çıkarılmadı | OCF reconciliation içinde. |
| Tüm legal/reserve adjustments | Blanket add-back yok | Tekrar edebiliyor; accrual ile cash ayrımı eksik. |
| Driver/courier/merchant promosyonları | Korundu | İşletmenin sürdürülmesi için recurring olabilir. |
| Buybacks | Economic FCF'den tekrar düşülmedi | SBC offset ile çifte sayım; sermaye kullanım kararı. |
| Acquisitions/equity/AV commitments | Operating normalization'a keyfi yıllık kesinti yok | Amount/timing/partner share açıklama sınırı; dağıtılabilir nakitte ayrıca ele alınmalı. |
| H1 yıllıklaştırma | Yapılmadı | Seasonality, settlements, M&A ve tax timing. |
| Yönetimin acquisition accretion/gross leverage beklentisi | Gerçekleşme sayılmadı | Şarta bağlı forward-looking sonuç. |

## 12. Evidence gaps ve stop record

| Açık alan | Neyi bilmiyoruz? | Sonuca etkisi | Bu pass'te durum |
|---|---|---|---|
| Insurance | Tam net premiums/paid claims/recoveries ve accident-year payout profili | Exact normalized cash claims hesaplanamaz. | Muhafazakâr gross float testi, kesin tahmin yok. |
| Incentives | Saf driver/courier subsidy, merchant bazında promosyon/advertising getirisi, teşviksiz retention | Marj artışından organik subsidy-free büyümeye atlanamaz. | UNCERTAIN; promosyon add-back'i yok. |
| AV contracts | Nihai Uber/fleet financing, guarantees, residual value/recourse | Tarihsel capex gelecekteki ekonomik sermaye gereksinimini eksik temsil edebilir. | OPEN. |
| Delivery Hero financing | Eylül final bond pricing/closing ve nihai acquisition finansmanı | Mevcut net debt ile future pro forma debt ayrılmalı. | S10/S11 taahhütleri ayrı; tamamlanmamış veriyle pro forma yok. |
| Legal/restructuring | Cash payment yılı, net reserve release ve yeni charge ayrımı | Tek seferlik add-back'lerin sürdürülebilirliği. | Yalnızca açık236 Foodpanda nakit düzeltmesi. |
| Long-run cash tax | NOL kullanım hızı, ülke kâr karması ve nihai mature rate | %10–15 bandı sürekli durum garantisi değil. | Yönetim bandı tarihsel duyarlılık olarak kullanıldı. |

**Durum:** Pass 2 tamamlandı. **Finansal tez:** MOSTLY YES; güven orta. **Pass 3 araştırma zamanı:** değerli, ancak başlatılmadı. İlerlemeyi, araştırma sonucunu ve yatırım/portföy kararını birbirinden ayrı tuttuk. Pass 1 dosyaları ile ana proje mimarisi değiştirilmedi.
