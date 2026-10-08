# Position Sizing — Policy / Calculation Component

Status: CORE ROLE DEFINED / POLICY PARAMETERS OPEN / NOT IMPLEMENTED

## Architecture Decision

Position Sizing, high-cost AI research protocolü değildir. Tercih edilen yaklaşım **policy-driven / calculation-heavy component**'tir. Bu dosya component'in sorumluluğunu ve policy sınırını kaydeder; sayısal yatırım politikası veya executable hesaplama implementation'ı oluşturmaz.

Sizing mümkün olduğunca explicit rules üzerinden hesaplanmalıdır. AI gerekli olduğunda risk / uncertainty ve uygunluk judgment'ı sağlar, fakat onaylı limitleri keyfi biçimde değiştirmez veya yalnız conviction üzerinden ağırlık üretmez.

## Conceptual Inputs

- Available capital
- Current portfolio weight
- Maximum asset exposure
- Asset risk
- Thesis confidence
- Valuation attractiveness
- Volatility
- Liquidity
- Portfolio overlap / concentration
- Position role
- Downside risk

Research, valuation ve [Portfolio Fit](../protocols/portfolio-fit.md) çıktıları tekrar araştırılmadan kullanılır. Geçerli policy referansı, portfolio context tarihi ve hesaplama tabanı anlaşılır olmalıdır. Mevcut pozisyon ağırlığı ile önerilen ek sermaye ayrı tutulur; cash veya düşünülen satış geliri iki kez sayılmaz.

## Policy and Calculation Boundary

Component uygun policy ve context ile hedef aralığı ve limitleri hesaplamaya yöneliktir. Policy eksik, çelişkili veya önemli girdiler yetersizse keyfi rakamla boşluk doldurulmaz; eksik constraint / policy ve gerekli review belirtilir. Draft allocation veya geçmiş örnek yüzdeler aktif max-position kuralı olmaz.

Risk-budget framework, max-position rules, conviction representation, volatility treatment ve sizing policy configuration henüz belirlenmemiştir. Bunların açık olması component'in kavramsal rolünü engellemez; güvenilir gerçek sizing çıktısı için ilgili policy ve girdilerin belirlenmesi gerekir.

## Conceptual Outputs

- Target position range
- Initial position size
- Maximum position size
- Staged-entry suggestion
- Sizing rationale
- Constraints hit

Range-based sizing tercih edilebilir; false precision üretilmez. Yalnız temsili biçim örneği, onaylı policy veya gerçek pozisyon önerisi değildir:

```text
Target Position: 5–7%
Initial Entry: 3%
Max Exposure: 7%
```

Buradaki yüzdeler aynı tanımlanmış portfolio tabanına göre pozisyon ağırlığı örneğidir. Gerçek çıktıda toplam hedef pozisyon ile ek alım tutarı ve kullanılan payda açık olmalıdır. AI tek başına gerekçesiz %7.34 gibi sonuç üretmemelidir.

Compact calculation / Machine Record konsept olarak kullanılan context, policy referansı, inputs, hesap gerekçesi, output ranges ve constraints hit bilgisini taşıyabilir; Human Brief önerilen aralık ile sınırlayıcı nedeni açıklar. Exact schema veya formül seti bu belgede tasarlanmaz.

## Technical Review and Execution

Position Sizing → Technical Review ayrımı korunur: sizing sermaye / exposure sınırlarını, Technical Review entry timing, zones ve technical context'i ele alır. Staged-entry miktar önerisi sizing'e; teknik fiyat bölgeleri ve zamanlama Technical Review'a aittir. Teknik bulgular planı etkilerse sizing constraints tekrar kontrol edilebilir; technical signal policy limitlerini aşma yetkisi vermez.

Position Sizing trade execution gerçekleştirmez. BUY CANDIDATE, ADD, uygun fit veya sizing planı otomatik işlem değildir; final authority kullanıcıdadır. Staged-entry sizing ve diğer açık policy konuları [Open Design Questions](../architecture/open-design-questions.md) içinde tutulur.
