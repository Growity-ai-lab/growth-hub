# CLAUDE.md — Growth Hub

Bu dosya Claude Code'un her oturumda okuduğu bağlamdır. Projeye yeni başlayan biri gibi davran:
önce burayı, sonra `README.md`'yi oku.

---

## 1. Proje ne işe yarıyor

Time & Growity (Türk dijital medya ajansı) bir müşteri kampanyasını hayata geçirirken onlarca
yayıncıya bütçe dağıtıyor. Bugün bu dağıtım kurumsal hafızaya değil, kişisel ilişkilere ve
o anki sezgiye dayanıyor. Growth Hub bunu değiştiriyor:

1. Biten kampanyaların **gerçekleşen** raporları standart bir şablona alınır
2. Sistem yayıncıların hangi sektörde, hangi yayın türünde nasıl performans verdiğini öğrenir
3. Yeni brief geldiğinde yayıncı ve bütçe önerir
4. Ekip öneriden sapabilir ama **sebebini yazmak zorundadır**; sapmalar kayda geçer

Time's Hub'ın (ölçüm) Growity tarafındaki karşılığı olarak konumlanıyor. Ürün ailesi:
Veri Enstitüsü (kitle) → A.T.L.A.S (hedefleme) → **Growth Hub (seçim)** → Time's Hub (ölçüm).

**Asıl çözülen problem teknik değil davranışsal:** ekibin ilişkisi iyi olduğu yayıncıya fazla
bütçe ayırmasını engellemek. Bu yüzden sapmayı yasaklamıyoruz, görünür kılıyoruz.

---

## 2. Değişmez mimari kurallar

Bunlar tercih değil, sözleşme. Bir istek bunlardan birini bozuyorsa önce uyar.

**K1 — Üç katman, tek yönlü akış.**
Kayıt (`/sablon`, `/donusturucu`, `/veri`) → Bilgi (`/puanlama`) → Karar (`/arayuz`).
Aşağıdan yukarı okunur, yukarıdan aşağı yazılmaz.

**K2 — Kodda gömülü isim ve eşik olmaz.**
Yayıncı adları, yayın türleri, sektörler, fiyat tipleri ve tüm parametreler
`sozluk/sozluk.xlsx` içindedir. Koda sabit bir yayıncı adı ya da eşik yazmak regresyondur.

**K3 — Her sayı tek yerde hesaplanır.**
Puan ve önerilen birim maliyet yalnızca `puanlama/skor.py` içinde üretilir. Arayüz ve
raporlar okur, yeniden hesaplamaz.

**K4 — Şablon dondurulmuştur.**
24 aylık migrasyon bitene kadar `sablon/TG_Yayin_Plani_Sablonu_v1.xlsx`'e kolon eklenmez.
İstekler `dokuman/sablon-v2-istekleri.md`'ye yazılır.

**K5 — Yeni özellik yerleştirme testi.**
Geçmişi mi kaydediyor → kayıt. Geçmişten çıkarım mı → bilgi. Geleceği mi etkiliyor → karar.
İkisine birden giriyorsa özellik ikiye bölünmüştür; böl.

**K6 — Ekibe görünen her metin sade Türkçe.**
Arayüz, şablon ve doküman metinlerinde jargon yok. "İndeks" değil "puan", "güven aralığı"
değil "ne kadar emin olduğumuz", "konsantrasyon" değil "bütçe yığılması".

---

## 3. Alan bilgisi — yeniden türetme, buradan al

### Eski raporlardan çıkarım kuralları
Ajansın eski Excel raporlarında fiyat tipi ve tutarın kaynağı yazmıyor. İkisi de çıkarılıyor:

- **Fiyat tipi:** `tutar / (birim_fiyat × adet)` oranı ≈ 0,001 ise **CPM**; ≈ 1 ise birim başı.
  Birim başıysa sözlükteki "beklenen fiyat tipi" kullanılır; o CPM ise kampanya amacına bakılır
  (trafik/satış → CPC, diğer → CPV). Oran hiçbirine uymazsa birim fiyat ≥ 5 → CPM.
- **Tutar nereden geldi:** gerçekleşen birim maliyet plandan %0,5'ten fazla farklıysa gerçek
  ölçüm var (`Platform Raporu`), aynıysa tutar plandan türetilmiş (`Hesaplanan`).
  Bu ayrım kritik: `Hesaplanan` satırlarda fiyat sapması yapısal olarak ölçülemez.
- **Tarih:** kampanya dönemi metninden ("15 Mayıs- 15 Haziran") türetilir. Sonuç bugünden
  ileriyse bir önceki yıl varsayılır.

### Puanlama
- Karşılaştırma havuzu: **sektör L2 + fiyat tipi + ana yayın türü**. Video işi hiçbir zaman
  tıklama işiyle karşılaştırılmaz. Havuzda `peer_havuzu_min` satırdan az varsa tüm sektörlere
  çekilir ve bu kullanıcıya söylenir.
- İndeks = havuz medyanı / satırın etkin birim maliyeti × 100. 100 = ortalama.
- Ağırlık = `log(1 + harcama) × 0.5^(ay / zaman_yari_omru_ay)`.
- Puan, `cekme_katsayisi` ile 100'e çekilir (az veri → puan ortalamaya yapışır).
- Güven aralığı yarı genişliği = `14 + 62/√n`. Arayüzde çubuk olarak gösterilir; **geniş çubuk
  az veri demektir ve bu sistemin en önemli mesajıdır.**
- Karne hücresi = sektör L2 × yayıncı grubu × yayıncı × ana yayın türü × fiyat tipi.

### Öneri motoru
- Aday havuzu → puana göre sıralama → kısıtlı bütçe dağıtımı.
- `tek_grup_tavani` (%30) tek yayıncı grubuna sınır koyar.
- `deneme_payi` (%8) az veri olan yayıncılara ayrılır. **Bu kota kaldırılmamalı:** olmazsa
  sistem kendi geçmişinin kopyasına döner ve yeni yayıncı asla şans bulmaz.
- Birim maliyet ve bütçe elle değiştirilebilir; `uyari_esigi`'ni (%15) aşan sapmada sebep sorulur.
- Onaylanan plan gerekçeleriyle dışa aktarılır (sistemin gerekçesi + kullanıcının sebebi).

---

## 4. Veri sözleşmesi

`donustur.py` → `donusum.json`: kampanya listesi. Her kampanya:

```
dosya, marka, kampanya, s1, s2, s3, bas, bit, tarih_kesin, yil, butce, uyari[], satirlar[]
```

Her satır:

```
grup, mecra, mecra_ham, ana_tur, reklam_modeli, format, site, hedef, cihaz, amac,
tip, tip_kaynak, plan_birim, plan_hacim, plan_bedel,
ger_hacim, ger_birim, ger_bedel, tik, vcr, ahb, adserver,
kaynak, durum, sozlukte_yok, bas, bit, satir_tarih, kaynak_dosya
```

`reklam_modeli`: K sütunundaki `format`'tan `sozluk` "Standart reklam modeli" eşlemesiyle türetilir;
eşleme boşsa `ana_tur`'e düşer. **Şablona yazılmaz** (K4) — puanlama bunu `donusum.json`'dan okur.

`durum` ∈ {Planlandı, Yayınlandı, İptal, Veri Gelmedi}. **Yalnızca `Yayınlandı` satırlar
puanlamaya girer** — yayınlanmamış planı sıfır performans saymak yayıncıya haksızlıktır.

`skor.py` → `karne.json`: hücre listesi, alanları için `puanlama/skor.py` sonundaki `sonuc.append`.

---

## 5. Regresyon testleri — her değişiklikten sonra

Çalıştırılabilir suite: **`python3 testler/regresyon.py`** (hepsi GEÇTİ olmalı). Aşağıdaki
maddeler o testlerin karşılığıdır.

1. **Toplam korunuyor mu:** her dönüştürülmüş şablonun `Kampanya!C26` değeri kaynak raporun
   gerçekleşen toplamına eşit olmalı. Sekiz dosyada da fark 0,00 ₺ olmalı.
   Referans: 25.676.102 ₺ toplam, 132 satır, 8 kampanya.
2. **Şablon formülleri hatasız:** `python3 /mnt/skills/public/xlsx/scripts/recalc.py <dosya>` →
   `total_errors: 0`. (LibreOffice yoksa `formulas` python kütüphanesiyle de doğrulanabilir.)
3. **Dönüştürücü çıktısı sabit:** kod değişikliği öncesi/sonrası `donusum.json` diff'i al.
   Beklenmeyen fark varsa dur ve raporla. (Reklam modeli eklendiğinde beklenen tek fark
   satır başına `reklam_modeli` anahtarıdır — geri kalan birebir aynı.)
4. **Parametreler bağlı mı:** `zaman_yari_omru_ay` 18 → 3 yapıldığında karne hücrelerinin
   bir kısmının puanı değişmeli (referans: 92 hücrenin 9'u). Değişmiyorsa parametre kopmuş.
5. **Sözlük eksikleri:** `donustur.py` sonunda "SÖZLÜKTE YOK" satırı çıkmamalı.
6. **Kırılım kapalı = bugün:** `karne_kirilim='ana tür'` iken çıktı bugünküyle birebir aynı
   (92 hücre, reklam_modeli==ana tür'e çöker, güven eşiğini geçen 1/92).
7. **Kırılım açık = dürüst incelme:** `karne_kirilim='reklam modeli'` iken hücre sayısı artar
   (97), her çocuk hücre `n ≤ ebeveyn`, `aralık ≥ ebeveyn`, az veri "kendi verisi" demez.
8. **Öneri tavanları:** öneri motoru Σ ≤ bütçe, grup payı ≤ `tek_grup_tavani`, min yayıncı
   bütçesi ve format çeşidi kurallarına uyar. **Karar defteri** yalnız-ekleme; eşik üstü
   sapması olup sebebi boş bir `secim` reddedilir.

---

## 6. Mevcut durum

- 8 kapanış raporu dönüştürülmüş (Uludağ ×3, Bitaksi ×2, Dardanel, TLC Klima, Züber)
- 132 satır, 4 sektör, 46 yayıncı, 92 karne hücresi (ana tür kırılımı)
- **Reklam modeli kırılımı** eklendi: `sozluk` "Standart reklam modeli" + `karne_kirilim`
  parametresi. `reklam modeli` seçiliyken karne 97 hücreye çıkar; puan geri çekilmeli havuzla
  (reklam modeli → ana tür → yayıncı → grup) hesaplanır, güven çubuğu dürüst kalır. Varsayılan
  `ana tür` (bugünkü davranış). Aç/kapat Excel'de bir politika kararı (K2).
- **Fayda = Puan × Yayınlanma%** karnede hesaplanır; öneri motoru bununla sıralar.
- **Öneri motoru gerçek:** `arayuz/oneri.py` karneyi okur, fayda/maliyete göre yayıncı × reklam
  modeli × fiyat tipi planı üretir (tek_grup_tavani/deneme_payi/min_yayinci_butcesi/
  min_format_cesidi). **Platform filtresi:** `yayinci_filtre` / `reklam_modeli_filtre` ile
  yalnız belirli yayıncılar istenebilir; filtre aktifken grup tavanı ve deneme payı gevşer
  (tek yayıncıya odak) ve kullanıcıya not düşülür. Filtresiz davranış birebir korunur.
- **Güven eşiğini geçen hücre: 92'de 1.** Bu bir kusur değil, veri azlığının dürüst yansıması.
- **Arayüz gerçek ve canlı** (mock-up değil). Kaynak paylaşımlı: `arayuz/pages/index.html` +
  `app.js`. Motoru besleyen `MOTOR` barındırmaya göre değişir:
  - **Yerel:** `arayuz/sunucu.py` (Python stdlib, sıfır bağımlılık) — fetch ile gerçek motora bağlar.
  - **GitHub Pages:** `arayuz/pages/motor-boot.js` gerçek `oneri.py`'ı tarayıcıda **Pyodide**
    ile koşturur (K3 — mantık yeniden yazılmaz). `arayuz/pages_uret.py` motor dosyalarını
    `arayuz/pages/motor/`'a kopyalar; `.github/workflows/pages.yml` karne/sözlük değişince
    yeniden yayınlar. Canlı: https://growity-ai-lab.github.io/growth-hub/
  - Serbest bütçe girişi + canlı **bütçe-etki geri bildirimi** (sapma ±%/₺ + tahmini hacim +
    toplam bütçe uyumu). Eski `growth-hub-mockup.html` (sahte `oneriUret` JS) artık geçersiz.
- **Karar defteri merkezi:** "Planı kaydet" kararları **Supabase Postgres**'e yazar
  (`arayuz/pages/app.js` → REST, anon key + RLS yalnız-ekleme, sebep-zorunlu DB trigger).
  Supabase yapılandırılmazsa JSONL indirmeye düşer. Şema: `supabase/migrations/`,
  kurulum: `dokuman/supabase-kurulum.md`. Yerel `arayuz/kararlar.py` (JSONL) hâlâ mevcut.

## 7. Sıradaki işler (öncelik sırasıyla)

1. **24 aylık migrasyon.** En büyük iş ve sistemin işe yaraması bunun bitmesine bağlı.
   Yeni şablon varyantı çıkarsa `donustur.py`'daki başlık eşleştirmesini genişlet, gömülü
   isim ekleme (K2). Reklam modeli kırılımının değeri de veri arttıkça ortaya çıkar.
2. **Reklam filmi kodu.** Eski raporların hiçbirinde yok, yeni kampanyalarda zorunlu tutulmalı.
   Bu olmadan kötü sonucun yayıncıdan mı reklam filminden mi geldiği ayrıştırılamaz.
3. **"Öneriden farklar" raporu.** Merkezi defter (Supabase `kararlar`) kuruldu ve yazıyor;
   sıradaki iş onu **geri okuyup** "ekip en çok nerede, hangi gerekçeyle sapıyor" tablosunu
   çıkarmak. Mimari kısıt: anon anahtar **yalnız-ekleme** (RLS) — güvenli okuma için Supabase
   Auth ya da `service_role` tutan küçük bir servis (ör. Render) gerekir; anon anahtara okuma
   yetkisi VERME (public sayfada tüm defter açığa çıkar).
4. **Karne ekranı + çok-adım akış.** Öneri akışı canlı; eksik olan Karne'yi (mecra karnesi,
   güven çubukları) ayrı bir ekran olarak göstermek ve akışı Yükle → Karne → Plan + iki rapor
   (Genel bakış, Öneriden farklar) biçimine oturtmak. Eski `arayuz/growth-hub-mockup.html`
   (sahte `oneriUret` JS) artık geçersiz — temizlenebilir.
5. **Time's Hub bağlantısı.** Uzun vade: puanlama "gerçekleşen KPI" yerine "artımsal katkı"
   üzerinden yapılırsa karne çok daha savunulabilir olur.

## 8. Tuzaklar

- **Ödül döngüsü:** iyi puanlı yayıncıya çok bütçe → çok veri → puanı daha da sağlamlaşır.
  Deneme payı bunun panzehiri; kaldırma.
- **Kreatif karışması:** aynı yayıncı kötü reklam filmiyle kötü görünür. Reklam filmi kodu
  girilmeden yayıncı performansı kreatif performansından ayrılamaz.
- **Ekip direnci:** sistem "denetim aracı" olarak algılanırsa veri kalitesi kasten bozulur.
  Dilin ve arayüzün tonu bu yüzden suçlayıcı değil.
- **Aşırı ayrıştırma:** yayın türüne göre bölmek doğru ama her bölme hücre başına veriyi
  inceltiyor. Yeni bir kırılım eklemeden önce hücre başına düşen satır sayısına bak.
