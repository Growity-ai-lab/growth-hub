# Growth Hub

Mecra seçim sistemi. Geçmiş kampanyaların gerçekleşen sonuçlarından öğrenir, brief geldiğinde
yayıncı ve bütçe önerir, öneriden sapmaları gerekçesiyle birlikte kaydeder.

## Üç katman, tek yönlü akış

    KAYIT           →      BİLGİ           →      KARAR
    "ne oldu"              "ne öğrendik"          "ne yapacağız"
    /sablon                /puanlama              /arayuz
    /donusturucu           karne.json             plan, sapma, export
    /veri                  Mecra_Karnesi.xlsx

**Aşağıdan yukarı okunur, yukarıdan aşağı yazılmaz.** Karar katmanı kampanya bitince bir
kapanış raporu üretir; o rapor kayıt katmanına ancak şablondan ve doğrulamadan geçerek girer.
Döngü böyle kapanır.

## Klasörler

| Klasör | İçerik | Kim dokunur |
|---|---|---|
| `/sozluk` | `sozluk.xlsx` (yayıncılar, yayın türleri, sektörler, fiyat tipleri, parametreler) + `sozluk.py` yükleyici | Ekip (Excel), CDO (parametreler) |
| `/sablon` | Standart yayın planı şablonu | Kilitli — v1 dondurulmuştur |
| `/donusturucu` | `donustur.py` (eski raporları okur), `sablon_doldur.py` (şablona yazar) | Geliştirici |
| `/veri` | `/ham`, `/donusturulmus`, `/birlesik` | Otomatik üretilir |
| `/puanlama` | `skor.py` + üretilen karne | Geliştirici |
| `/arayuz` | Mock-up, sonra uygulama | Geliştirici |
| `/dokuman` | Ekip kılavuzu, alınan kararlar | CDO |

## Değişmez kurallar

**1. Kod içinde isim ve eşik gömülü olmaz.** Yayıncı adları, yayın türleri, sektörler,
fiyat tipleri ve tüm parametreler `sozluk.xlsx` içindedir. Yeni bir yayıncıyla çalışıldığında
ya da eski raporda yazım hatası bulunduğunda kod değil, o Excel güncellenir.

**2. Her sayı tek bir yerde hesaplanır.** Puan ve önerilen birim maliyet yalnızca
`/puanlama/skor.py` içinde üretilir; arayüz ve raporlar onu okur, yeniden hesaplamaz.

**3. Şablon dondurulmuştur.** 24 aylık migrasyon bitene kadar kolon eklenmez. Her şablon
değişikliği daha önce dönüştürülmüş dosyaları geçersiz kılar. Eksik alanlar
`/dokuman/sablon-v2-istekleri.md` dosyasına yazılır, migrasyondan sonra tek seferde açılır.

**4. Yeni özellik nereye gider — üç soru:**
- Geçmişte olmuş bir şeyi mi kaydediyor? → kayıt katmanı
- Geçmişten çıkarılan bir sonuç mu? → bilgi katmanı
- Gelecekteki bir seçimi mi etkiliyor? → karar katmanı

İkisine birden giriyorsa o özellik ikiye bölünmüştür; bölün.

## Çalıştırma

```bash
# 1) eski kapanış raporlarını dönüştür
cd donusturucu
python3 donustur.py ../veri/ham            # -> /tmp/donusum.json, sözlükte olmayan adları raporlar
python3 sablon_doldur.py                   # -> ../veri/donusturulmus/*.xlsx

# 2) karneyi hesapla
cd ../puanlama
python3 skor.py /tmp/donusum.json .        # -> karne.json + Mecra_Karnesi.xlsx

# 3) brief için mecra planı öner (fayda/maliyet)
cd ../arayuz
python3 oneri.py --sektor "İçecek" --amac "Gösterim almak" --butce 4200000

# 4) canlı arayüzden test et (tarayıcı, sıfır bağımlılık)
python3 sunucu.py                          # -> http://localhost:8000
```

`sunucu.py` mockup'ın aksine gerçek motora bağlıdır: karneyi `karne.json`'dan okur, planı
`oneri.py` ile üretir, sapma + sebebi karar defterine yazar. Tarayıcıdaki hiçbir sayı yeniden
hesaplanmaz (K3); menüler karne + sözlükten dolar (K2). Eşik üstü sapmada sebep boşsa kayıt reddedilir.

Karnenin kırılım seviyesi `sozluk.xlsx` → Parametreler → `karne_kirilim` ile seçilir:
`ana tür` (varsayılan) ya da `reklam modeli` (skippable/bumper/masthead/trueview ayrı puanlanır).
Regresyon: `python3 testler/regresyon.py`.

`donustur.py` her çalışmasında sözlükte bulamadığı adları listeler. O listedeki her ad
`sozluk.xlsx`'e eklenene kadar ilgili satırlar gruplanamaz — rapor bozulmaz, sadece o satır
karneye katkı vermez.

## Parametreler ajans politikasıdır

`sozluk.xlsx` → Parametreler sayfası. Bunlar teknik ayar değil, yönetim kararıdır:
tek gruba en fazla bütçe payı, deneme payı, uyarı eşiği, güven eşiği, zaman yarı ömrü,
çekme katsayısı. Değiştirildiğinde puanlar bir sonraki hesaplamada değişir.

Doğrulanmış örnek: zaman yarı ömrü 18 aydan 3 aya çekildiğinde 92 karne hücresinin 10'unun
puanı değişiyor. Yani parametre gerçekten bağlı, kozmetik değil.

## Bilinen borçlar

- Reklam filmi kodu eski raporların hiçbirinde yok. Yeni kampanyalardan itibaren
  şablonda zorunlu tutulmalı, yoksa kötü sonucun yayıncıdan mı reklam filminden mi
  geldiği ayrıştırılamaz.
- Görünürlük ve satır bazlı tarih eski raporlarda yok; tarihler kampanya döneminden türetiliyor.
- Karar katmanı (öneri geçmişi, sapma kayıtları) henüz veritabanına yazmıyor; mock-up aşamasında.
- Güven eşiğini geçen hücre sayısı çok düşük. 24 aylık migrasyon tamamlanmadan
  öneriler "tahmin" seviyesinde kalır.
