# PortfolioMind UI/UX Tasarım Kararları ve Yol Haritası

**Tarih:** 2026-09-16  
**Durum:** Ürün Felsefesi ve Arayüz Mimarisi Belirlendi (Geliştirme Öncesi Tasarım Aşaması)  
**Temel Belgeler:**
- `PORTFOLIOMIND_INTEGRATION_CONTEXT.md` (Mevcut kod ve veri sınırları - Baseline)
- `PORTFOLIOMIND_DASHBOARD_OPERATING_MODEL.md` (Ana Dashboard Çalışma Modeli ve Felsefesi)

---

## 1. Giriş ve Ürün Vizyonu

PortfolioMind, klasik bir net değer takipçisinin (NetWorth) ötesine geçerek yatırımcının bir **"Kişisel Yatırım Karar ve Zeka İstasyonu"** haline gelmesini hedefler.

* **NetWorth Sorusu:** *"Neye sahibim?"*
* **PortfolioMind Soruları:**
  - *"Neye sahibim?"*
  - *"Buna neden sahibim (Tezim ne)?"*
  - *"Ne değişti?"*
  - *"Dikkatimi gerektiren bir şey var mı?"*
  - *"Yatırım tezim hâlâ geçerli mi?"*
  - *"Şu anda neyi araştırıyorum?"*
  - *"Portföyüm genelinde hangi riskler var?"*
  - *"Hangi önemli olaylar/kazanç raporları yaklaşıyor?"*
  - *"Portföyüm hedef dağılımımdan saptı mı?"*
  - **"Neyi güvenle görmezden gelebilirim?"**

### Temel İlke: Gürültüyü Azaltmak, Sessiz Karar Desteği Sağlamak
Piyasa ekranı klonu (Bloomberg, TradingView) ya da sürekli akan bir haber/fiyat şeridi olmak yerine; binlerce piyasa olayını süzüp yalnızca portföyü ve tezi gerçekten etkileyen 1-2 kritik konuyu öne çıkaran, **"Bugün yapacak hiçbir şey yok, her şey yolunda"** sonucunu da bir başarı olarak sunabilen düşük gürültülü (low-noise) bir karar destek merkezi.

---

## 2. Navigasyon Mimarisi (Sidebar)

Mevcut sol menü, sorumlulukları net bir hiyerarşiye kavuşturularak evrilecektir:

```
PORTFOLIOMIND
Investment Intelligence

OVERVIEW
- Dashboard          (Genel bakış, Portfolio Pulse, dikkat gerektirenler)

PORTFOLIO            [ Neye sahibim? ]
- Holdings           (Mevcut varlıklar, pozisyonlar)
- Allocation         (Mevcut vs Hedef Dağılım, sapma analizi)
- Cash               (Nakit hesapları ve hareketler)

INTELLIGENCE         [ Neyi değerlendiriyorum ve izliyorum? ]
- Watchlist          (Alım aralığı beklenen veya izlenen enstrümanlar)
- Research           (Araştırma hattı / pipeline)
- Monitoring         (Tez kontrolleri, olaylar, haber radarı)

DECISIONS            [ Neden bu kararı aldım? ]
- Journal            (Yatırım günlüğü, karar gerekçeleri ve geçmişi)

SYSTEM
- Settings           (Tercihler, para birimi, entegrasyonlar)
```

---

## 3. Ana Dashboard Çalışma Modeli

*(Detaylı manifesto için bknz: `PORTFOLIOMIND_DASHBOARD_OPERATING_MODEL.md`)*

### A. Global Üst Bar (Quiet Top Bar)
- **Evrensel Arama:** Ticker, şirket adı, araştırma kaydı veya konu arama.
- **Sağ Araçlar:** Para birimi seçimi (TRY/USD/EUR), bildirimler, kullanıcı hesabı.

### B. Portfolio Pulse (Durum Katmanı)
Dashboard başlığının hemen altında, 5 saniyede durumu özetleyen 4 kritik sayaç:
1. **Material Events (Önemli Gelişmeler):** Portföyü etkileyen haber/bilanço sayısı.
2. **Thesis Alerts (Tez Uyarıları):** Tezi gözden geçirme gerektiren varlıklar.
3. **Upcoming Earnings (Yaklaşan Olaylar):** Önümüzdeki 7 gün içindeki kritik tarihler.
4. **Allocation Drift (Dağılım Sapması):** Hedef dağılımdan yüzdesel sapma durumu.

### C. Birincil Satır (Finansal Durum & Hedef Dağılım)
- **Total Portfolio Value:** NetWorth'ün kanıtlanmış toplam servet kartı, P&L ve zaman grafiği.
- **Portfolio Allocation (Current vs. Target):** Yalnızca mevcut dağılımı değil; kullanıcının belirlediği **Hedef Dağılım** ile kıyaslamayı ve sapmayı (drift) gösteren halka grafik.

### D. İkincil Satır (Zeka ve Eylem Odaklı Kartlar)
- **Needs Attention (Dikkat Gerektirenler):** Sadece fiyat düştü/çıktı diye değil, temel bir olay (mevzuat değişikliği, bilanço revizyonu, aşırı volatilite) olduğunda tetiklenen aksiyon kartı.
- **Research Queue (Araştırma Hattı):** Aktif incelenen hisselerin kompakt durumu (`Researching`, `Waiting for Price`, `Ready`, `Review`).
- **Upcoming Events (Yaklaşan Olaylar):** Portföydeki şirketlerin bilançoları, temettüleri, Fed kararları gibi kritik takvim.

### E. Üçüncül Satır (Fırsatlar, Risk ve Karar Geçmişi)
- **Watchlist Opportunities:** Değerlemesi veya fiyatı alım aralığına yaklaşan izleme listesi hisseleri.
- **Portfolio Context & Risk:** Anlamlı risk göstergeleri (Sektör yoğunlaşması örn: %38 Teknoloji, para birimi riski, en büyük pozisyon).
- **Recent Journal Entries:** Yakın zamanda alınan kararların ve tez güncellemelerinin özeti.

---

## 4. Varlık Detay Ekranı (`/assets/:id`) Mimarisi

Bir pozisyona tıklandığında yalnızca bir muhasebe tablosu değil, o varlığın **neden sahip olunduğunu ve gelecekte ne yapılacağını** gösteren strateji ekranı:

1. **Aksiyon Kutusu (The Verdict):**
   - Karar Rozeti: `HOLD`, `BUY / ADD`, `SELL / REDUCE`, `REVIEW_REQUIRED`.
   - AI / Analist Özeti (Human Brief): 2-3 cümlelik net durum değerlendirmesi.
2. **Fiyat & Strateji Aralıkları (Buy / Sell Zones):**
   - `TechnicalPlan` modelinden beslenen görsel bir barem:
     - `Stop / İptal Bölgesi` < `Alım / Ekleme Bölgesi` < `(Mevcut Fiyat)` < `Kâr Al / Satış Bölgesi`.
3. **İnceleme & Tez Geçmişi (Intelligence Timeline):**
   - Şirket hakkında yapılan geçmiş analizler, araştırma notları, protokol koşuları.
4. **Finansal Detaylar & İşlemler:**
   - TradingView grafiği, maliyet/kâr-zarar metrikleri ve geçmiş BUY/SELL işlemleri.

---

## 5. İsteğe Bağlı Piyasa İstihbarat Bülteni (On-Demand Briefing)

- **Tetikleme:** Kullanıcı istediğinde çalışan ("Piyasa Raporunu Getir") isteğe bağlı (on-demand) araştırma mekanizması.
- **Kapsam:**
  1. Portföyümdeki Hisseler
  2. İzleme Listem (Watchlist)
  3. Makroekonomik Gelişmeler
- **Çıktı Biçimi:** Gürültüsüz, maddeler halinde, portföy üzerindeki etkisini (`Pozitif`, `Risk`, `Nötr`) belirten kompakt özetler.

---

## 6. Yapay Zeka (AI) Etkileşim Felsefesi

- Ekranda devasa bir "Chat with AI" kutusu **olmayacak**.
- AI, arayüzün her yerine yayılmış **bağlamsal ve uzmanlaşmış** bir analitik katman olarak çalışacaktır:
  - Dashboard'da: *"Portföyümdeki ortak risk faktörü nedir?"*
  - Hissede: *"Son bilanço orijinal yatırım tezimi bozdu mu?"*
  - Araştırmada: *"Benim bu hisse hakkındaki varsayımlarımı zorla / antitez üret."*

---

## 7. Uygulama Öncesi Kurallar

> [!CAUTION]
> **KOD DEĞİŞİKLİĞİ YOK:** Bu aşamada hiçbir kod yazılmayacak, bileşen veya route oluşturulmayacak, veritabanı şeması değiştirilmeyecektir.
> Tüm bu başlıklar tasarım, bilgi mimarisi ve UX prototipi olarak kullanıcı ile tartışılarak olgunlaştırılacaktır.
