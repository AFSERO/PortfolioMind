# News Monitoring

Status: DESIGN IN PROGRESS

## Purpose

Portfolio ve gerektiğinde watchlist için yeni haberleri düzenli olarak taramak ve yalnızca yatırım tezini veya portföy kararını etkileyebilecek gelişmeleri öne çıkarmak.

News Monitoring pahalı deep research değildir. Ana görevi:

```text
New Information
→ Filter
→ Deduplicate
→ Verify when possible
→ Materiality assessment
→ Review trigger
```

## Planned Trigger

Preferred future cadence: **Approximately every 8 hours**.

Bu cadence henüz aktif değildir. 12 saat gibi alternatifler ileride değerlendirilebilir.

SCHEDULE STATUS: NOT ACTIVE

Sistem implement edilip test edilene kadar scheduled task, automation, cron veya calendar event oluşturulmayacaktır.

## Materiality

İlk taslak sınıflandırma:

### LOW

Düşük yatırım önemi.

- Kaydedilebilir.
- Kullanıcıya bildirim gerekmez.
- Research protocol tetiklenmez.

### MEDIUM

Bilmek yararlı olabilir.

- Sonraki Human Brief / digest içinde gösterilebilir.
- Otomatik deep review gerektirmez.

### HIGH

Investment thesis veya önemli portfolio decision üzerinde etkili olabilir.

- İlgili review protocol önerilebilir.
- Örneğin Earnings Review, Single Asset Monitoring, Thesis Review veya Valuation Update.

## Verification Status

Materiality ile source confidence ayrı tutulmalıdır.

### HIGH + VERIFIED

Önemli gelişme credible/primary/professional kaynaklarla doğrulanmışsa ilgili review protocol için trigger/recommendation oluşturulabilir.

### HIGH + UNVERIFIED

X/Twitter, sosyal medya veya doğrulanmamış haberlerde önemli bir iddia ortaya çıkarsa:

- Investment recommendation üretme.
- Otomatik thesis değişikliği yapma.
- Kullanıcıya `REVIEW REQUESTED` bildirimi oluştur.

Yalnızca örnek çıktı; gerçek bir olay veya yatırım değerlendirmesi değildir:

```text
UBER — REVIEW REQUESTED

Claim:
Major AV partnership may be ending.

Source status:
UNVERIFIED

Potential thesis impact:
HIGH

Action:
Verify before investment decision.
```

## Social Media Principle

X/Twitter ve benzeri kaynaklar:

> Low-confidence radar, potentially high-value signal.

olarak kullanılabilir. Social media tamamen göz ardı edilmemelidir. Ancak material investment claims mümkün olduğunca company IR, SEC/KAP, regulator, official source veya Reuters/Bloomberg/FT gibi professional sources ile doğrulanmaya çalışılmalıdır.

## Relationship to Portfolio Monitoring

News Monitoring sık, düşük maliyetli ve değişiklik tespit odaklı olmalıdır. Portfolio Monitoring'den ayrı çalışır; Portfolio Monitoring daha kapsamlı değerlendirme yapabilir.

Planlanan ilişki:

```text
News Monitoring
      ↓
Material Event?
      ├── NO → Stop
      └── YES
            ↓
      Review Trigger
            ↓
Relevant Protocol
```

Portfolio Monitoring'in her 8 saatte bir full çalıştırılması planlanmamaktadır. Bu ilişki gelecekteki tasarım yönelimidir; aktif protocol execution veya automation değildir.

## Outputs

Mevcut dual-output principle geçerlidir.

### Machine Record

DESIGN PENDING

Muhtemel alanlar ileride:

- Timestamp
- Affected asset
- Event
- Source
- Verification status
- Materiality
- Potential thesis impact
- Recommended next protocol

Bu liste kesin schema değildir; schema henüz tasarlanmayacaktır.

### Human Brief

Yalnızca gerçekten önemli gelişme varsa kısa bildirim. Önemli gelişme yoksa kullanıcı gereksiz yere rahatsız edilmemelidir. MEDIUM gelişmeler sonraki Human Brief / digest içinde gösterilebilir; tek başına ayrı bildirim gerektirmez.
