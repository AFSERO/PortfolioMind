# UBER — Valuation model
**Kesit:** 14 Eylül 2026. **Fiyat:** $71.62; kaynak ekranı 10:06 EDT / 17:06 Türkiye. Bu intraday snapshot'tır; kapanış fiyatı değildir. **Birim:** aksi yazılmadıkça milyar USD; hisse sayıları milyar adet. Ondalık ayıracı noktadır. Hesaplar yuvarlanmadan, tablolar yuvarlanarak oluşturuldu.

[Ana rapor](research-report.md) · [Kaynak kaydı](source-register.md)

## 1. Girdiler, tarih ve valuation perimeter

| Girdi | Değer | Tarih / kaynak | Kullanım |
|---|---:|---|---|
| Share price | $71.62 | 14.09.2026, 10:06 EDT; N01 | Sabit fiyat snapshot'ı |
| Gerçek outstanding shares | 2.042560121 | 31.07.2026; U02 kapak | Market cap için en yeni doğrulanmış adet |
| Q2 diluted weighted-average shares | 2.050225 | Q2 2026; U02 EPS | Valuation paydası proxy; spot fully diluted count değildir |
| H1 diluted weighted-average shares | 2.060763 | H1 2026; U02 | Dönemsel FCF/share kontrolü; market cap paydası değil |
| Market cap | 146.288 | Fiyat × Temmuz outstanding; hesap | Eylül'deki açıklanmamış buyback/issuance dahil değil |
| Diluted payda ile equity karşılığı | 146.837 | Fiyat × 2.050225; hesap | Reverse DCF hedefi için |
| Cash and equivalents | 4.870 | 30.06.2026; U02 | Unrestricted |
| Short-term investments | 0.521 | 30.06.2026; U02 | Cash-like |
| Cash + short-term investments | 5.391 | U02; hesap | Restricted kalemleri içermez |
| Borrowings, book carrying value | 12.723 | 30.06.2026; U02 | Nominal / piyasa değeriyle aynı değil |
| Net debt | 7.332 | 12.723 − 5.391 | Finance/operating lease yükünü aşağıdaki nakit yaklaşımından ayrı düşün |
| Redeemable + diğer NCI | 1.083 | 0.180 + 0.903; U02 | Konsolide operasyon değerinden çıkarılan book-value proxy |
| Operating lease liabilities | 2.008 | 30.06.2026; U02 | Ayrı bilgi; lease gideri/ödemesi FCF'de kalıyor |
| Restricted cash / investments | 11.793 | 0.661 + 1.646 + 9.486; U02 | Excess cash değil; EV'den düşülmedi |
| Insurance reserves | 13.286 | 3.758 + 9.528; U02 | Banka borcu gibi ikinci kez EV'ye eklenmedi |
| Operating cash buffer | 2.000 | Analist varsayımı | 5.391'in tümünü dağıtılabilir saymamak için |
| Non-operating assets, seçilen net değer | 10.000 | Aşağıdaki haircut hesabı | Fair value gerçeği değil; 7–12B duyarlılık |
| Cash buffer sonrası excess cash | 3.391 | 5.391 − 2.000 | DCF equity bridge |

**Üç ayrı EV tanımı:**

- Holdings düşülmeden conventional consolidated EV = 146.288 + 7.332 + 1.083 = **154.703**.
- Non-operating assets ayrılmış operating EV = 154.703 − 10.000 = **144.703**. Operating multiple tablosunun payı budur.
- DCF için fiyatın gerektirdiği operating EV = 146.837 + 7.332 + 1.083 + 2.000 − 10.000 = **147.252**. Diluted payda ve korunacak operating cash bu tanıma dahildir.
- DCF equity bridge = operating EV + 10.000 + 3.391 − 12.723 − 1.083 = **operating EV − 0.415**.
- Değer/share = equity value / **2.050225**.

Bilanço 30 Haziran, outstanding Temmuz, fiyat Eylül kesitidir; bu bir Eylül bilanço tahmini değildir. NCI'nin ekonomik değeri, borcun piyasa değeri, son çeyrek cash accumulation ve buyback'ler tam güncellenemedi. $1B net bridge farkı yaklaşık **$0.49/share** değiştirir.

Borrowings tablosu lease liabilities'i kapsayan genel “total debt” veri sağlayıcısı tanımı değildir. Operating leases faaliyet gideri olarak, finance lease principal ise FCF içindeki nakit kullanımı olarak tutuldu; aynı lease yükümlülüğü bridge'de ikinci kez düşülmedi. Finance lease interest/yenileme nakdinin tamamen ayrıştırılamaması nedeniyle başlangıç FCFF'si tam bir lease-adjusted muhasebe mutabakatı değil, operating cash proxy'dir.

### Non-operating investments

Kaynak U02 Notes 2–3; aşağıdaki oranlar **analist varsayımıdır**. Haircut; vergi, likidite, private valuation, realizasyon ve dated-price riskini birlikte temsil eder; statutory tax hesaplaması değildir.

| Varlık | Son açıklanan tutar / taban | Korunan oran | Modele katkı |
|---|---:|---:|---:|
| Didi, private | 1.900 carrying | 50% | 0.950 |
| Diğer private equity | 2.263 carrying | 50% | 1.132 |
| Grab | 2.020 fair value | 80% | 1.616 |
| Aurora | 1.763 fair value | 80% | 1.410 |
| Diğer listed equities | 0.813 fair value | 80% | 0.650 |
| Delivery Hero doğrudan pay | 3.100 fair value; book 3.502 | 85% | 2.635 |
| Diğer equity-method | 0.124 book | 50% | 0.062 |
| Delivery Hero TRS | 1.500 carrying/fair value; nakit maliyet 1.640 değil | 75% | 1.125 |
| Loan / convertible receivables | 0.864 carrying | 75% | 0.648 |
| Careem Technologies | 0.147 Haziran equity-method | 0% ayrı varlık | 0.000 |
| **Haircut toplamı** | | | **10.228** |
| **Modelde yuvarlanmış tutar** | | | **10.000** |

Listed/private securities 8.759B + equity-method 3.773B = **12.532B** muhasebe toplamıdır. TRS ve loan receivables buna ayrıca gelir. DH book-to-fair farkı ve Careem'in Temmuzda yeniden konsolidasyonu dikkate alındı; ham 12.532B'yi doğrudan eklemek uygun değil. DH TRS, doğrudan %24.99 paydan ayrı exposure'dır; aynı pay iki kez sayılmadı. TRS tutarı 1.640B cash outflow yerine U02'deki 1.5B fair value ile alındı.

Aurora paylarının bir kısmının exchangeable notes için rehinli olması likiditeyi sınırlar. Borç zaten bridge'de olduğu için teminatın tamamı ayrıca sıfırlanmadı. Careem ayrı asset olarak sıfırlandı; işletme katkısı rolling forecast'ün içinde kabul ediliyor, küçük acquisition cash/goodwill farkı bridge belirsizliğinde.

**Asset duyarlılığı:** 7B / 10B / 12B non-operating değer, base merkez sonucunu yaklaşık **$68.08 / $69.54 / $70.52** yapar. Bu varlıklar material; yine de ana sonucu belirleyen operating cash growth ve terminal economics'tir.

### Eylül bond pricing: tamamlanma ile fiyatlama ayrımı

N04 nihai prospectus 9 Eylül tarihli, 11 Eylül'de filed; **€4.5B**, beş tranche, %3.75–5.25 coupon. Yaklaşık net proceeds **€4.453B**; beklenen settlement **15 Eylül**, dolayısıyla 14 Eylülde tamamlanmış cash/debt gibi kaydedilmedi. Belgedeki 9 Eylül EUR/USD **1.1652** kuru canlı FX değildir.

Belgenin June-basis pro forma'sı principal debt **12.625 → 17.868B**, cash **4.870 → 10.058B**. Böylece Pass 2'de açık kalan nominal debt toplamı 12.625B olarak netleşiyor; değerlemede doğrulanmış book 12.723B korunuyor. Aynı dönüşümü book-debt proxy'ye uygularsak cash+ST 10.579B, debt yaklaşık 17.966B, net debt **7.387B** olur: cash kullanılmadıkça net debt yalnız yaklaşık **0.055B** artar. Debt'i ekleyip proceeds'i unutmak da proceeds'i ücretsiz nakit saymak da yanlıştır.

Tam yıllık brüt coupon yaklaşık €0.200B / **$0.233B**; actual funding/carry/net interest farklı olabilir. FCFF interest öncesi olduğundan bu coupon ayrıca FCFF'den düşülmez; future equity-cash kontrolü ve finansman riskine aittir. Net proceeds kullanım amacı general corporate purposes; tümünü kesin DH harcaması saymadık.

## 2. Pass 2 kontrolü ve güncel TTM bridge

Kaynak gerçekleşmeler Pass 2 source register ve U01–U05. TTM = **FY2025 − H1 2025 + H1 2026**; yarıyıl ikiyle çarpılmadı.

| Kalem | FY2025 | H1 2025 | H1 2026 | TTM Haziran 2026 |
|---|---:|---:|---:|---:|
| Gross bookings | 193.454 | 89.574 | 111.742 | 215.622 |
| Revenue | 52.017 | 24.184 | 27.394 | 55.227 |
| GAAP EBIT | 5.565 | 2.678 | 3.813 | 6.700 |
| Adjusted EBITDA | 8.730 | 3.987 | 5.300 | 10.043 |
| OCF | 10.099 | 4.888 | 5.213 | 10.424 |
| Cash capex | 0.336 | 0.163 | 0.135 | 0.308 |
| Reported FCF | 9.763 | 4.725 | 5.078 | 10.116 |
| SBC | 1.826 | 0.910 | 1.023 | 1.939 |
| D&A, cash-flow reconciliation | 0.747 | 0.359 | 0.386 | 0.774 |
| Insurance reserve OCF contribution | 2.660 | 1.487 | 0.830 | 2.003 |
| Non-insurance WC contribution | -0.433 | -0.560 | -0.620 | -0.493 |
| Finance lease principal | 0.157 | 0.075 | 0.082 | 0.164 |
| Non-GAAP operating income | 6.453 | 2.860 | 4.026 | 7.619 |
| Interest expense | 0.440 | 0.213 | 0.235 | 0.462 |
| Interest income | 0.743 | 0.350 | 0.347 | 0.740 |
| Cash income tax paid | 0.345 | 0.167 | 0.280 | 0.458 |
| Net income attributable to Uber | 10.053 | 3.131 | 2.657 | 9.579 |

**Pass 2 FY2025 tekrar hesap:**

Tax proxy denominator = 6.453 − 0.440 + 0.743 = 6.756.
Incremental cash tax = 10–15% × 6.756 − 0.345 = **0.3306–0.6684**.

Normalized cash FCF = 9.763 − 2.660 − 0.157 + 0.236 − incremental tax
= **6.5136–6.8514**.

Shareholder economic FCF = normalized − 1.826 SBC
= **4.6876–5.0254**. Kullanıcının yaklaşık 6.5–6.9 / 4.7–5.0 çerçevesi aritmetik olarak doğrulandı.

**TTM güncellemesi:**

Tax proxy denominator = 7.619 − 0.462 + 0.740 = **7.897**.
Incremental cash tax = 10–15% × 7.897 − 0.458 = **0.3317–0.72655**.

Normalized cash FCF = 10.116 − 2.003 − 0.164 − incremental tax
= **7.22245–7.61730**.

Shareholder economic FCF = normalized − 1.939
= **5.28345–5.67830**.

Foodpanda'nın Nisan 2025 cash payment'ı TTM Temmuz 2025–Haziran 2026 dışında; TTM'ye yeniden eklenmedi. UK VAT'nin tahsil edilmemiş potansiyel iadesi sıfır add-back. DTA release ve investment revaluation OCF'de zaten ters çevrildiğinden tekrar düşülmedi.

Bu iki normalizasyon **gross insurance-float-neutral tanısal aralıktır**. Cash tax bandı dar olsa da toplam ekonomik belirsizlik dar değildir. Insurance recoverables/prepayments ile gross reserve cash movement tam eşleşmediği için bu, audited owner earnings değildir. Restricted assets artışı ayrıca çıkarılmadı.

## 3. Ana anchor ve pay başına kontrol

**Primary:** SBC gideri içeren GAAP EBIT'ten türetilmiş, insurance float büyümesine değer atamayan, operating economic FCFF proxy; bunu operating EV ile karşılaştır.

Başlangıç:
```text
Economic operating FCFF
= EBIT × (1 − cash tax rate)
  + D&A − cash capex − finance lease principal
  − normal non-insurance WC funding

= 6.700 × (1 − 12.5%) + 0.774 − 0.308 − 0.164 − 0.493
= 5.6715B
```

10–15% tax ile başlangıç **5.504–5.839B**. Net reinvestment başlangıçta 0.308 + 0.164 + 0.493 − 0.774 = **0.191B**. FCF'nin bu işletme formunda interest income ve non-operating investment getirisi yoktur; varlıklar bridge'de ayrıca değerlenir.

**Secondary:** 5.28–5.68B levered shareholder economic cash proxy ve diluted FCF/share. Bu nakit akışını equity ile karşılaştır; DCF'ye koyup net debt'i tekrar çıkarma. İki yöntem farklı vergi tabanı, accrual/non-cash ve interest perimeter içerir; 5.67B ile cash bridge orta noktasının birebir aynı olması beklenmez.

| TTM cash measure | FCF, $B | Q2 diluted payda ile $/share |
|---|---:|---:|
| Reported FCF | 10.116 | 4.93 |
| Normalized cash FCF, SBC öncesi | 7.222–7.617 | 3.52–3.72 |
| Shareholder economic cash proxy | 5.283–5.678 | 2.58–2.77 |
| Primary operating FCFF proxy | 5.672 | 2.77 |

Per-share değerler bugünkü valuation paydasına bölünmüş karşılaştırmadır; şirketin raporladığı TTM EPS gibi dönemsel weighted-average metrik değildir.

**SBC convention:** Gelecek EBIT marjları recurring SBC ücretini içerir; SBC tekrar FCF'den düşülmez. Sabit 2.050225B share count, gelecekteki ücretin nakit eşdeğer maliyetle karşılandığı allocation-neutral yaklaşımı temsil eder. Bu actual share-count forecast değildir. Hem SBC'yi çıkarıp hem aynı ödüller için sürekli dilution cezası ve buyback gideri yazmak double count olur. Mevcut diluted payda da options/RSU claims'in tam spot değerlemesi değildir; grant-date cost, vesting/forfeiture, tax deduction ve retention cash cost farkları confidence'ı sınırlar.

Buyback kendi başına operating value yaratmaz. Dağıtılan FCF'yi DCF'de sayıp bu nakitle azalan hisse sayısından ayrıca bedava kazanç eklenmedi. Cash-equivalent SBC'yi karşılamak için yeterli nakit harcanmasına rağmen net payda artıyorsa bu convention başarısız olur; güncel denominator ve ücret varsayımı birlikte güncellenmelidir.

## 4. Current multiples

| Ölçü | Hesap / sonuç | Yorum |
|---|---|---|
| P/E, TTM GAAP | 146.288 / 9.579 = **15.27x** | Tax benefit ve investment kazançları nedeniyle zayıf anchor |
| FY2026 forward P/E | 71.62 / 3.36 = **21.32x** | N03 adjusted consensus EPS; GAAP değil |
| FY2027 forward P/E | 71.62 / 4.41 = **16.24x** | N03 adjusted consensus EPS; gerçekleşme değil |
| EV / company Adjusted EBITDA | 154.703 / 10.043 = **15.40x** | Holdings dahil EV |
| Operating EV / Adjusted EBITDA | 144.703 / 10.043 = **14.41x** | SBC exclusion nedeniyle tek başına yeterli değil |
| Operating EV / SBC dahil EBITDA proxy | 144.703 / (6.700 + 0.774) = **19.36x** | EBITDA tanımını açık tutan kontrol |
| EV / EBIT | 154.703 / 6.700 = **23.09x** | Holdings dahil |
| Operating EV / EBIT | 144.703 / 6.700 = **21.60x** | P/E'den daha yararlı operating kontrol |
| P / Reported FCF | 146.288 / 10.116 = **14.46x** | Yield **6.92%** |
| P / Normalized cash FCF | **19.20–20.25x** | Yield **4.94–5.21%** |
| P / Shareholder economic FCF | **25.76–27.69x** | Yield **3.61–3.88%** |
| EV / Reported FCF | 154.703 / 10.116 = **15.29x** | Levered denominator nedeniyle yalnız geleneksel gösterim |
| Operating EV / economic FCFF | 144.703 / 5.6715 = **25.51x** | Perimeter eşleşen primary kontrol |
| Reverse target EV / economic FCFF | 147.252 / 5.6715 = **25.96x** | Cash buffer + diluted payda dahil |

FY2025 cash flow'larını Eylül fiyatıyla kullanırsak sırasıyla reported **14.98x**, normalized **21.35–22.46x**, economic **29.11–31.21x**. TTM güncellemesi iyileşmeyi kabul eder, fakat “14–15x FCF ile ucuz” iddiası owner-economics bazında ayakta kalmaz.

N01 sağlayıcı EV'si 151.03B ve aynı sayfadaki cash/debt/net cash satırları kendi aralarında tutarlı değil; bunun yerine yukarıdaki bridge kullanıldı. N03'ün dönem tanımı belirsiz “forward 17.15x” değeri alınmadı. Açık FY2026/FY2027 EPS'ler kullanıldı. N03 FCF forecast serisinin historical 2025 tabanı şirket FCF'siyle uyuşmadığından FCF consensus reverse model'e alınmadı.

## 5. Beş yıllık operating scenarios

Y1–Y5, valuation tarihinden itibaren yaklaşık 12 aylık forecast dönemleridir (Y1: Eylül 2027'ye, Y5: Eylül 2031'e kadar). Haziran TTM lagged başlangıç proxy'sidir; bu takvim FY2026/FY2027 consensus'u ile birebir aynı dönem değildir. Ara dönemi tahmini çeyreklerle doldurup precision yaratılmadı.

Bütün forecast girdileri **analist varsayımı**, company guidance değildir. Revenue/bookings muhasebe sunum oranıdır; ekonomik take rate sayılmaz. Economic FCFF = bookings × [EBIT/bookings × (1 − tax) − net reinvestment/bookings].

Net reinvestment; capex − D&A, finance lease principal, insurance dışı normal WC ve operasyonu destekleyen AV/teknoloji sermayesi için toplulaştırılmış net cash allowance'dır. Mevcut non-operating stakes'ten gelecek getiriler bu büyümeye eklenmedi. Base'te 4.39B beş yıllık net allowance, mevcut çok düşük cash capex'ten daha yüksek sermaye ihtiyacına yer açar; açıklanmamış fleet guarantees'i eksiksiz fiyatlamaz. Bear daha düşük hacme rağmen daha yüksek sermaye yükü taşır.

Bear: Mobility yavaşlar, Delivery leverage oluşmaz, insurance economics ve AV pazarlık gücü bozulur; tax normalleşirken nakit düşer. Base: mevcut konum korunur, bookings büyümesi kademeli yavaşlar, Delivery ve merkez giderlerde leverage sürer. Bull: güçlü organik hacim, reklam/Delivery monetization ve AV dağıtım rolü marjları destekler; araç ekonomisinin çoğu partnerlerde kalır.

### Bear

| Girdi / çıktı | Y1 | Y2 | Y3 | Y4 | Y5 |
|---|---:|---:|---:|---:|---:|
| Bookings büyümesi | 10.0% | 8.0% | 7.0% | 6.0% | 5.0% |
| Gross bookings, $B | 237.18 | 256.16 | 274.09 | 290.54 | 305.06 |
| Revenue / bookings (muhasebe oranı) | 25.0% | 24.8% | 24.5% | 24.3% | 24.0% |
| Revenue, $B | 59.30 | 63.40 | 67.15 | 70.45 | 73.21 |
| EBIT / bookings; SBC dahil | 3.00% | 2.90% | 2.80% | 2.70% | 2.60% |
| EBIT / revenue | 12.0% | 11.7% | 11.4% | 11.1% | 10.8% |
| EBIT, $B | 7.12 | 7.43 | 7.67 | 7.84 | 7.93 |
| Cash tax / EBIT | 15.0% | 18.0% | 20.0% | 22.0% | 23.0% |
| Net reinvestment / bookings | 0.45% | 0.50% | 0.55% | 0.60% | 0.65% |
| Net reinvestment, $B | 1.07 | 1.28 | 1.51 | 1.74 | 1.98 |
| Normalized economic operating FCF, $B | 4.98 | 4.81 | 4.63 | 4.38 | 4.12 |
| Economic operating FCF / bookings | 2.10% | 1.88% | 1.69% | 1.51% | 1.35% |
| Economic operating FCF / revenue | 8.4% | 7.6% | 6.9% | 6.2% | 5.6% |
| Valuation share count, B | 2.050225 | 2.050225 | 2.050225 | 2.050225 | 2.050225 |
| Economic operating FCF / share, $ | 2.43 | 2.35 | 2.26 | 2.13 | 2.01 |

Beş yıllık CAGR: bookings **7.2%**, revenue **5.8%**, economic operating FCF **-6.2%**. Beş yılda net reinvestment 7.58B. FCF/share, sabit payda nedeniyle aynı CAGR ile değişir.

### Base

| Girdi / çıktı | Y1 | Y2 | Y3 | Y4 | Y5 |
|---|---:|---:|---:|---:|---:|
| Bookings büyümesi | 18.0% | 16.0% | 14.0% | 12.0% | 10.0% |
| Gross bookings, $B | 254.43 | 295.14 | 336.46 | 376.84 | 414.52 |
| Revenue / bookings (muhasebe oranı) | 25.0% | 25.0% | 25.0% | 25.0% | 25.0% |
| Revenue, $B | 63.61 | 73.79 | 84.12 | 94.21 | 103.63 |
| EBIT / bookings; SBC dahil | 3.50% | 3.80% | 4.10% | 4.30% | 4.50% |
| EBIT / revenue | 14.0% | 15.2% | 16.4% | 17.2% | 18.0% |
| EBIT, $B | 8.91 | 11.22 | 13.80 | 16.20 | 18.65 |
| Cash tax / EBIT | 13.0% | 15.0% | 17.0% | 20.0% | 23.0% |
| Net reinvestment / bookings | 0.15% | 0.20% | 0.25% | 0.30% | 0.35% |
| Net reinvestment, $B | 0.38 | 0.59 | 0.84 | 1.13 | 1.45 |
| Normalized economic operating FCF, $B | 7.37 | 8.94 | 10.61 | 11.83 | 12.91 |
| Economic operating FCF / bookings | 2.90% | 3.03% | 3.15% | 3.14% | 3.12% |
| Economic operating FCF / revenue | 11.6% | 12.1% | 12.6% | 12.6% | 12.5% |
| Valuation share count, B | 2.050225 | 2.050225 | 2.050225 | 2.050225 | 2.050225 |
| Economic operating FCF / share, $ | 3.59 | 4.36 | 5.17 | 5.77 | 6.30 |

Beş yıllık CAGR: bookings **14.0%**, revenue **13.4%**, economic operating FCF **17.9%**. Beş yılda net reinvestment 4.39B. FCF/share, sabit payda nedeniyle aynı CAGR ile değişir.

### Bull

| Girdi / çıktı | Y1 | Y2 | Y3 | Y4 | Y5 |
|---|---:|---:|---:|---:|---:|
| Bookings büyümesi | 23.0% | 21.0% | 18.0% | 16.0% | 14.0% |
| Gross bookings, $B | 265.22 | 320.91 | 378.67 | 439.26 | 500.76 |
| Revenue / bookings (muhasebe oranı) | 25.5% | 25.5% | 25.5% | 25.5% | 25.5% |
| Revenue, $B | 67.63 | 81.83 | 96.56 | 112.01 | 127.69 |
| EBIT / bookings; SBC dahil | 3.70% | 4.20% | 4.70% | 5.10% | 5.50% |
| EBIT / revenue | 14.5% | 16.5% | 18.4% | 20.0% | 21.6% |
| EBIT, $B | 9.81 | 13.48 | 17.80 | 22.40 | 27.54 |
| Cash tax / EBIT | 12.0% | 14.0% | 17.0% | 20.0% | 23.0% |
| Net reinvestment / bookings | 0.20% | 0.25% | 0.30% | 0.35% | 0.40% |
| Net reinvestment, $B | 0.53 | 0.80 | 1.14 | 1.54 | 2.00 |
| Normalized economic operating FCF, $B | 8.10 | 10.79 | 13.64 | 16.38 | 19.20 |
| Economic operating FCF / bookings | 3.06% | 3.36% | 3.60% | 3.73% | 3.84% |
| Economic operating FCF / revenue | 12.0% | 13.2% | 14.1% | 14.6% | 15.0% |
| Valuation share count, B | 2.050225 | 2.050225 | 2.050225 | 2.050225 | 2.050225 |
| Economic operating FCF / share, $ | 3.95 | 5.26 | 6.65 | 7.99 | 9.37 |

Beş yıllık CAGR: bookings **18.4%**, revenue **18.3%**, economic operating FCF **27.6%**. Beş yılda net reinvestment 6.01B. FCF/share, sabit payda nedeniyle aynı CAGR ile değişir.

## 6. DCF ve terminal consistency

```text
NOPAT5 = EBIT5 × (1 − 23%)
Terminal reinvestment rate
  = max(g / incremental ROIC, Y5 net reinvestment / NOPAT5)
FCFF6 = NOPAT5 × (1 + g) × (1 − terminal reinvestment rate)
TV5 = FCFF6 / (WACC − g)
Operating EV = Σ[FCFFt / (1 + WACC)^t] + TV5 / (1 + WACC)^5
Equity = Operating EV − 0.415
Value/share = Equity / 2.050225
```

Terminal vergi tüm senaryolarda %23; düşük NOL/cash tax avantajı sonsuza kadar uzatılmadı. Terminal büyüme sermaye gerektirir: ROIC 15/25/30% varsayımları incremental net capital üzerindeki, SBC sonrası getiridir; ölçülmüş historical Uber ROIC değildir. Y5 reinvestment floor'u, özellikle bear'da Y6'da sermaye yükünün kendiliğinden ortadan kalkmasını önler.

WACC %9–12.5 aralığı risk/reward hurdle varsayımıdır; bugünkü Treasury+beta formülünden kesin hesaplanmış WACC iddiası yoktur. Daha güçlü moat ve finansman esnekliği daha düşük hurdle, daha zayıf economics daha yüksek hurdle gerektirir. USD nominal cash flows, nominal discount/g ile eşleşir; midpoint değerler olasılık ağırlıklı hedef fiyat değildir.

| Senaryo | WACC bandı | Terminal g | Terminal incremental ROIC | Operating EV, $B | Equity, $B | Bugünkü değer/share | $71.62'ye göre |
|---|---|---|---|---:|---:|---:|---:|
| Bear | 10.5%–12.5% | 1.5%–2.5% | 15.0% | 37.62–49.40 | 37.21–48.98 | $18.15–23.89 | -74.7% / -66.6% |
| Base | 9.5%–11.5% | 2.5%–3.5% | 25.0% | 121.93–174.05 | 121.52–173.64 | $59.27–84.69 | -17.2% / +18.3% |
| Bull | 9.0%–11.0% | 3.0%–4.0% | 30.0% | 194.05–299.60 | 193.64–299.18 | $94.45–145.93 | 31.9% / +103.8% |

Aralık uçları eşzamanlı WACC/g kombinasyonlarıdır, istatistiksel güven aralıkları değildir. Büyük zarar/büyük kazanç olasılıklarını atamadan ortalamak “beklenen getiri” üretmez.

| Senaryo; merkez varsayım | Y1–5 FCF PV | Terminal FCF Y6 | Terminal value Y5 | Terminal PV | Terminal / EV | Değer/share |
|---|---:|---:|---:|---:|---:|---:|
| Bear; WACC 11.5%, g 2.0% | 16.90 | 4.21 | 44.28 | 25.70 | 60.3% | $20.58 |
| Base; WACC 10.5%, g 3.0% | 37.63 | 13.02 | 173.58 | 105.37 | 73.7% | $69.54 |
| Bull; WACC 10.0%, g 3.5% | 49.64 | 19.39 | 298.29 | 185.21 | 78.9% | $114.35 |

Base değerinin **%74'ü terminal**. Yaklaşık $70 merkezi değer, yüksek güvenli nokta tahmini olarak sunulamaz. Beş yıllık organic büyümenin sonrasında competition/AV veya capital intensity değişirse değer hızla değişir.

### Base operating path için WACC / g duyarlılığı

| WACC \ terminal g | 2.0% | 3.0% | 4.0% |
|---|---:|---:|---:|
| 9.5% | $73.08 | $80.73 | $89.36 |
| 10.5% | $64.03 | $69.54 | $75.30 |
| 11.5% | $56.89 | $61.00 | $65.00 |

Bu tabloda yalnız discount/terminal assumptions değişir; operating forecast sabittir. Daha yüksek g, terminal reinvestment'ı da artırır.

### Normalized FCF multiple ve EBITDA kontrolü

Y5 economic FCFF'ye seçilen exit multiple uygulanır; Y1–5 cash flow PV ayrıca dahil edilir. Y5 equity value bugünkü fiyatla doğrudan karşılaştırılmaz.

| Senaryo | Y5 economic FCFF exit multiple | Bugüne indirgenmiş değer/share | Bu exit EV'nin SBC dahil EBITDA çarpanı |
|---|---:|---:|---:|
| Bear | 10–14x | $19.71–24.38 | 4.8–6.7x |
| Base | 14–18x | $71.67–86.96 | 9.2–11.8x |
| Bull | 18–23x | $128.70–157.78 | 12.0–15.3x |

SBC dahil EBITDA proxy = Y5 GAAP EBIT + Y5 revenue'nun %1'i D&A varsayımı. Bunlar forward peer medyanı değildir. Örneğin base DCF midpoint, Y5 FCFF'nin **13.44x** ve SBC dahil EBITDA'nın **8.82x** terminal EV'sini ima eder. Multiple kontrolü base'te $72–87 ile daha olumlu; güçlü terminal kalitesine bağımlıdır. Ana DCF aralığı bununla keyfi biçimde yükseltilmedi.

## 7. Reverse valuation

Hedef operating EV **147.252B**, başlangıç economic FCFF **5.6715B**. İlk beş yılda sabit FCF CAGR olan c çözülür:

```text
147.252 = Σ[t=1..5] 5.6715 × (1+c)^t / (1+WACC)^t
          + [5.6715 × (1+c)^5 × (1+g)/(WACC−g)]/(1+WACC)^5
```

Burada terminal FCF zaten sürdürülebilir reinvestment/tax sonrası kabul edilir. Bu basitleştirilmiş reverse kimliği, ayrı EBIT/ROIC tabanlı forward DCF ile birebir aynı tahmin değildir. Makul bir sonuç için margin/capital testini ayrıca geçmelidir.

**Gerekli beş yıllık economic FCF CAGR:**

| WACC \ terminal g | 2.5% | 3.0% | 3.5% |
|---|---:|---:|---:|
| 9.5% | 16.5% | 14.9% | 13.3% |
| 10.5% | 20.2% | 18.8% | 17.3% |
| 11.5% | 23.6% | 22.4% | 21.1% |

Merkez %10.5 WACC / %3 g: **%18.79 CAGR**, Y5 **13.42B**, mevcut 5.67B'nin **2.37 katı**. Tabloda yaklaşık %13–24 gereksinim, discount/terminal riskinin önemini gösterir.

| Beş yıl bookings CAGR varsayımı | Y5 bookings | Gerekli FCF / bookings | FCF / revenue; revenue/GB %25 | Yaklaşık gerekli EBIT / bookings |
|---|---:|---:|---:|---:|
| 10% | 347.26 | 3.86% | 15.45% | 5.47% |
| 14% | 415.16 | 3.23% | 12.93% | 4.65% |
| 18% | 493.29 | 2.72% | 10.88% | 3.99% |

Son sütun %23 terminal tax ve Y5 net reinvestment/GB %0.35 varsayımıyla (FCF margin + 0.35%)/77%. Başlangıç EBIT/GB **3.11%**, FCF/GB **2.63%**. Böylece fiyat, düşük bookings büyümesinde çok daha güçlü margin genişlemesi ister. Tek başına “%19 büyüme fiyatlanıyor” denklemi bir piyasa consensus ölçümü değildir; alternatif growth/margin patikaları aynı fiyatı verebilir.

**Sınıflama:** düşük discount ucunda reasonable; merkezde **reasonable-to-demanding**, muhafazakâr hurdle'da demanding. **Conservative expectations** değil; **extremely demanding** demek için de kanıt yok. Başarı yalnız robotaxi tekeli gerektirmiyor, fakat sıradan düşük büyüme ve sabit marj da yeterli olmuyor.

N03 secondary consensus: FY2026 revenue **57.89B** (+11.3%), FY2027 **66.79B** (+15.4%); adjusted EPS **3.36 / 4.41**. Bu beklenti operating leverage ile uyumlu; UK accounting effect nedeniyle revenue büyümesi bookings beklentisi değildir. Base Y1 revenue 63.61B rolling döneminde; calendar consensus ile karıştırılmadı.

## 8. AV, capital allocation ve diğer material sensitivities

AV etkisini izole etmek için base tax path, %10.5 WACC, %3 g, holdings bridge ve share count sabit tutuldu.

| AV durumu | Base'e göre yıllık bookings büyümesi farkı | Y5 EBIT/GB | Yıllık net reinvestment/GB farkı | Y5 FCFF | Değer/share |
|---|---:|---:|---:|---:|---:|
| Negative: müşteri ilişkisi/provider gücü Uber aleyhine | -2.5 puan | 3.50% | +0.20 puan | 7.96 | $45.49 |
| Neutral / Hybrid | 0 | 4.50% | 0 | 12.91 | $69.54 |
| Positive: demand aggregation güçlenir | +1.5 puan | 5.25% | +0.15 puan | 15.68 | $84.02 |

Margin farkı Y1'den Y5'e doğrusal oluşur; positive için terminal incremental ROIC %30, negative %15, hybrid %25. Terminal reinvestment floor korunur. Positive AV sermayesiz kabul edilmedi. Bunlar Pass 1 MIXED sonucunun sayısal **stress test'leri**, robotaxi sözleşmelerinden çıkarılmış tahminler değildir. Full bear/bull, AV dışında Mobility/Delivery/insurance ve finansman riskini de değiştirir; bu tablo full scenario bandını tekrarlamaz.

**M&A perimeter:** Delivery Hero closing öncesi standalone Uber forecast + mevcut DH stake/TRS asset değeri. İleride acquired bookings otomatik olarak eklenmedi. Deal gerçekleşirse mevcut stake/TRS'nin tasfiyesi/dönüşümü, ödenecek incremental consideration, acquired net debt, retained/carved-out assets ve yeni FCF birlikte konsolide edilmelidir. Full offer headline'ını bugünkü net debt'e ekleyip acquired business'ı sıfır saymak da hatalıdır.

Tamamlanacak deal'in **incremental NPV** stress'i -5 / 0 / +3B seçilirse mevcut base $69.54 → **$67.10 / $69.54 / $71.01**. Bunlar ölçülmüş synergy veya purchase-price estimate değildir. Ana tabloda **0 NPV** merkezi convention kullanıldı; ownership exposure'un bugün ayrıca sayılması korunur. Bu, deal'in risksiz olduğu anlamına gelmez: leverage kaynaklı daha yüksek WACC'nin etkisi ayrıca daha büyük olabilir. Funding capacity kullanılmamışken drawn debt sayılmadı.

| İlave stress; diğerleri aynı | Yaklaşık değer etkisi |
|---|---:|
| Beş yıl her yıl +1B ek net cash burden | -$1.83/share |
| Bugünden itibaren kalıcı düz 1B/yıl ek burden, %10.5 hurdle | -$4.65/share |
| One-off 1B cash outflow, bugünkü değer | -$0.49/share |
| Ana FCF proxy başlangıcı ±1B; aynı reverse hurdle | Gerekli CAGR belirgin değişir; tek normalized FCF rakamına güvenilmemeli |

Extra AV guarantees, restructuring ve pending smaller M&A harcamaları net reinvestment/bridge'i aşarsa bu sensitivity uygulanır; aynı cash item hem EBIT marjında hem burada tekrar düşülmez. UK VAT iadesi alınırsa yalnız net gerçekleşen tutar ve ileriye etkisi eklenir.

## 9. Fundamental margin of safety

Base bandı yaklaşık **$59–85**, merkez $69.54. $71.62 merkezden yaklaşık %3 yüksek; bandın iyimser ucuna göre %18 upside, alt ucuna göre %17 downside. Bu, güçlü margin of safety değildir.

**$50–55**, unchanged base economics'e göre yaklaşık **%21–28 discount** verir; mevcut 5.48B economic cash midpoint'ine göre yield yaklaşık **%4.9–5.4**. $55–60, finansal kalitenin/marjların daha güçlü teyidiyle yeniden değerlendirme bandıdır; koşulsuz cazip değer iddiası değildir. Bear $18–24 olduğu için $50–55 de permanent capital loss'u dışlamaz. Bunlar fundamental araştırma eşikleridir.

## 10. Yeniden üretim ve kontrol

Bu dosyadaki decimal girdiler, formüller ve yıllık tablolar hesabı yeniden üretmek için yeterlidir. DCF yıl sonu discount convention kullanır; midyear yöntemi uygulanmadı. Sonuçlar deal NPV=0, assets=10B, cash buffer=2B ve fixed valuation shares=2.050225B ile üretildi. Base manual örnek:

```text
Y1 GB = 215.622 × 1.18 = 254.43396
Y1 EBIT = 254.43396 × .035 = 8.9051886
Y1 FCFF = 8.9051886 × .87 − 254.43396 × .0015 = 7.365863142
Y5 NOPAT = 18.65353470495 × .77 = 14.36322172279
Terminal reinvestment = max(.03/.25, 1.45083047705/14.36322172279) = .12
Y6 FCFF = 14.36322172279 × 1.03 × .88 = 13.01882416956
TV5 = 13.01882416956 / .075 = 173.58432226075
PV(Y1–5) = 37.62720368039
PV(TV) = 105.36566391670
Operating EV = 142.99286759709
Equity = 142.57786759709
Value/share = 69.54254659713
```

Kontrol: cash-flow bridge, dönemsel toplama, net-debt/holdings ayrımı, SBC'nin tek sayılması, terminal reinvestment, discounting ve per-share aritmetiği doğrulandı. Bu aralıklar araştırma kararı içindir; order, allocation veya entry planı değildir.

## Kaynak bağlantıları

- **U01:** [Uber 2025 10-K](https://www.sec.gov/Archives/edgar/data/1543151/000154315126000015/uber-20251231.htm).
- **U02:** [Uber Q2 2026 10-Q](https://www.sec.gov/Archives/edgar/data/1543151/000154315126000032/uber-20260630.htm).
- **U03:** [Uber FY2025 sonuçları](https://investor.uber.com/news-events/news/press-release-details/2026/Uber-Announces-Results-for-Fourth-Quarter-and-Full-Year-2025/).
- **U04:** [Uber Q2 2026 sonuçları](https://investor.uber.com/news-events/news/press-release-details/2026/Uber-Announces-Results-for-Second-Quarter-2026/default.aspx).
- **U05:** [Uber Q2 prepared remarks](https://investor.uber.com/files/doc_earnings/2026/q2/transcript/Uber-Q2-26-Prepared-Remarks.pdf).
- **N01:** [UBER price/statistics snapshot](https://stockanalysis.com/stocks/uber/statistics/).
- **N03:** [UBER FY consensus](https://stockanalysis.com/stocks/uber/forecast/).
- **N04:** [Uber final eurobond prospectus](https://www.sec.gov/Archives/edgar/data/1543151/000155278126000481/e26382_uber-euro424b2.htm).

