# -*- coding: utf-8 -*-
"""
T&G Growth Hub — Öneri motoru (Karar katmanı).

Tek işi: brief geldiğinde mecra karnesinden (puanlama/karne.json) fayda/maliyet dengesine
göre bir yayın planı ÖNERMEK. Puanı, faydayı ya da önerilen birim maliyeti burada YENİDEN
HESAPLAMAZ (K3) — hepsini karneden okur. Tüm eşikler sozluk.xlsx'ten gelir (K2).

Grain: yayıncı × reklam modeli × fiyat tipi (karne hücresi).

Kullanım:
    python3 oneri.py --sektor "İçecek" --amac "Gösterim almak" --butce 4200000
    python3 oneri.py --sektor "Hazır Yiyecek" --amac "Video izletmek" --butce 3000000 --format-cesidi 4
"""
import argparse, json, math, os, sys, datetime, collections

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'sozluk'))
from sozluk import Sozluk
import kararlar

KOK_DIZIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KARNE = os.path.join(KOK_DIZIN, 'puanlama', 'karne.json')
SOZLUK = os.path.join(KOK_DIZIN, 'sozluk', 'sozluk.xlsx')


def _amac_video_haritasi(sz):
    """Sözlükten amaç → video mu (çoğunluk) haritası çıkarır. Kod içinde politika gömmez (K2)."""
    say = collections.defaultdict(lambda: [0, 0])   # amaç -> [video_degil, video]
    for t in sz.turler.values():
        say[t['amac']][1 if t['video'] else 0] += 1
    return {a: (v[1] >= v[0]) for a, v in say.items()}


def _grupla_yuvarla(x, taban=1000):
    return int(round(x / taban) * taban)


def _adaylar(brief, karne, sz):
    """Sektör + amaç uyumuna göre aday hücre havuzunu (fayda'ya göre sıralı) döndürür.

    Filtreden ve bütçeden bağımsızdır; hem oneri_uret hem filtre_secenekleri kullanır.
    """
    havuz_min = int(sz.p('peer_havuzu_min', 3))
    amac_video = _amac_video_haritasi(sz)
    video_brief = amac_video.get(brief['amac'], False)
    uyarilar = []

    def amac_uyar(c):
        return sz.yayin_turu(c.get('ornek_tur') or '')['video'] == video_brief

    sektor = [c for c in karne if c['s2'] == brief['sektor_l2']]
    sektor_geri = False
    if len(sektor) < havuz_min:
        sektor = list(karne)
        sektor_geri = True
        uyarilar.append('Bu sektörde yeterli veri yok; öneri tüm sektörlerin verisinden çekildi.')

    adaylar = [c for c in sektor if amac_uyar(c)]
    if not adaylar:                       # amaç filtresi her şeyi elerse geri çekil
        adaylar = sektor
        uyarilar.append('Amaç filtresine uyan hücre bulunamadı; tüm uygun hücreler değerlendirildi.')

    adaylar.sort(key=lambda c: (-c['fayda'], c['yayinci'], c['reklam_modeli']))
    return adaylar, uyarilar, sektor_geri


def _uygula_filtre(adaylar, yayinci_filtre, reklam_modeli_filtre):
    """Katı platform filtresi. yayinci_filtre boşsa dokunmaz.

    reklam_modeli_filtre = {yayinci: [izinli reklam modelleri]} (boş liste = hepsi).
    Dönüş: (süzülmüş adaylar, filtre_aktif).
    """
    if not yayinci_filtre:
        return adaylar, False
    yset = set(yayinci_filtre)
    rmf = reklam_modeli_filtre or {}
    out = []
    for c in adaylar:
        if c['yayinci'] not in yset:
            continue
        izin = rmf.get(c['yayinci'])
        if izin and c['reklam_modeli'] not in set(izin):
            continue
        out.append(c)
    return out, True


def filtre_secenekleri(brief, karne, sz):
    """Bu sektör+amaç için seçilebilir yayıncılar ve her birinin reklam modelleri.

    Arayüzün platform filtresini sözlük/karneden doldurur (K2 — kodda gömülü liste yok).
    """
    adaylar, _u, _g = _adaylar(brief, karne, sz)
    m = {}
    for c in adaylar:
        m.setdefault(c['yayinci'], set()).add(c['reklam_modeli'])
    return {y: sorted(v) for y, v in sorted(m.items())}


def oneri_uret(brief, karne, sz):
    """brief={sektor_l2, amac, toplam_butce, istenen_format_cesidi?,
             yayinci_filtre?, reklam_modeli_filtre?} → plan sözlüğü."""
    tavan = float(sz.p('tek_grup_tavani', 0.30))
    deneme_payi = float(sz.p('deneme_payi', 0.08))
    min_butce = float(sz.p('min_yayinci_butcesi', 50000))
    min_format = int(brief.get('istenen_format_cesidi') or sz.p('min_format_cesidi', 3))
    cekirdek_min_n = int(sz.p('cekirdek_min_n', 2))
    cekirdek_adet = int(sz.p('cekirdek_adet', 6))
    deneme_esigi = float(sz.p('deneme_indeks_esigi', 104))
    deneme_adet = int(sz.p('deneme_adet', 2))
    uyari_esigi = float(sz.p('uyari_esigi', 0.15))
    butce = float(brief['toplam_butce'])

    adaylar, uyarilar, sektor_geri = _adaylar(brief, karne, sz)

    # --- platform / reklam modeli filtresi (katı; aktifse kurallar gevşer) ---
    adaylar, filtre_aktif = _uygula_filtre(
        adaylar, brief.get('yayinci_filtre'), brief.get('reklam_modeli_filtre'))
    if filtre_aktif:
        if not adaylar:
            uyarilar.append('Seçilen platform/reklam modeli için bu sektör+amaçta veri yok.')
        tavan = 1.0            # tek/az yayıncıya odak: grup bütçe tavanı kaldırılır
        deneme_payi = 0.0      # filtreliyken deneme payı uygulanmaz
        uyarilar.append('Platform filtresi aktif: grup bütçe tavanı ve deneme payı bu planda '
                        'uygulanmadı (yalnızca seçilen yayıncılara odaklanıldı).')

    # --- çekirdek / deneme ayrımı ---
    cekirdek = [c for c in adaylar if c['n'] >= cekirdek_min_n][:cekirdek_adet]
    cek_ids = {id(c) for c in cekirdek}
    if filtre_aktif:
        deneme = []
        if not cekirdek:      # seçilenlerin hepsi az-veri ise yine de plana girsinler
            cekirdek = adaylar[:cekirdek_adet]
    else:
        deneme = [c for c in adaylar
                  if id(c) not in cek_ids and c['n'] < cekirdek_min_n and c['puan'] >= deneme_esigi][:deneme_adet]

    # --- min_format_cesidi: filtre aktifken uygulanmaz (kullanıcı zaten daralttı) ---
    def modeller(cells):
        return {c['reklam_modeli'] for c in cells}
    if not filtre_aktif:
        secili = cekirdek + deneme
        for c in adaylar:
            if len(modeller(secili)) >= min_format:
                break
            if c['reklam_modeli'] not in modeller(secili):
                cekirdek.append(c); secili = cekirdek + deneme
        if len(modeller(secili)) < min_format:
            uyarilar.append(f'İstenen {min_format} reklam modeli çeşidine ulaşılamadı '
                            f'(veride {len(modeller(secili))} çeşit var).')

    # --- bütçe dağıtımı: ağırlık = fayda × √n, grup tavanı + min yayıncı bütçesi ---
    cekirdek_butce = butce * (1 - deneme_payi)
    grup_tavan_tl = butce * tavan

    # deneme payını önce böl; grup tavanı çekirdek + deneme TOPLAMINA uygulanmalı
    deneme_toplam = butce * deneme_payi
    dpay = {}
    if deneme:
        pd = deneme_toplam / len(deneme)
        for c in deneme:
            dpay[id(c)] = pd
    deneme_grup = collections.defaultdict(float)
    for c in deneme:
        deneme_grup[c['grup']] += dpay[id(c)]
    grup_cap = collections.defaultdict(lambda: grup_tavan_tl)
    for g, v in deneme_grup.items():                 # deneme grubun tavanından düşülür
        grup_cap[g] = max(0.0, grup_tavan_tl - v)

    def dagit(cells, toplam):
        if not cells:
            return {}
        agirlik = {id(c): max(c['fayda'], 1) * math.sqrt(c['n']) for c in cells}
        pay = {id(c): 0.0 for c in cells}
        aktif = list(cells)
        kalan = toplam
        for _ in range(30):                       # grup tavanını iteratif uygula
            tw = sum(agirlik[id(c)] for c in aktif) or 1
            for c in aktif:
                pay[id(c)] += kalan * agirlik[id(c)] / tw
            # grup toplamları tavanı aşıyor mu
            gtop = collections.defaultdict(float)
            for c in cells:
                gtop[c['grup']] += pay[id(c)]
            asan = {g: v for g, v in gtop.items() if v > grup_cap[g] + 1e-6}
            if not asan:
                break
            kalan = 0.0
            yeni_aktif = []
            for c in cells:
                if c['grup'] in asan:                # bu grubu tavana kırp, oran koru
                    pol = pay[id(c)] / gtop[c['grup']] if gtop[c['grup']] else 0
                    hedef = grup_cap[c['grup']] * pol
                    kalan += pay[id(c)] - hedef
                    pay[id(c)] = hedef
                else:
                    yeni_aktif.append(c)
            aktif = yeni_aktif
            if not aktif or kalan <= 1e-6:
                break
        return pay

    pay = dagit(cekirdek, cekirdek_butce)

    # min yayıncı bütçesi: altında kalanları düşür, bütçeyi kalan çekirdeğe yeniden dağıt
    dusen = [c for c in cekirdek if pay.get(id(c), 0) < min_butce]
    if dusen and len(dusen) < len(cekirdek):
        for c in dusen:
            uyarilar.append(f"{c['yayinci']} · {c['reklam_modeli']} min yayıncı bütçesinin "
                            f"altında kaldı, plandan düşürüldü.")
        cekirdek = [c for c in cekirdek if c not in dusen]
        pay = dagit(cekirdek, cekirdek_butce)

    # --- plan satırları ---
    def satir(c, tutar, deneme_mi):
        return dict(
            yayinci=c['yayinci'], grup=c['grup'], reklam_modeli=c['reklam_modeli'],
            ana_tur=c['tur'], tip=c['tip'], puan=c['puan'], fayda=c['fayda'], n=c['n'],
            aralik=c['aralik'], guven=c['guven'], kirilim_seviye=c.get('kirilim_seviye', 'ana tür'),
            oner=c['oner'], oner_kaynak=c['oner_kaynak'], oner_n=c['oner_n'],
            sistem_butce=_grupla_yuvarla(tutar), deneme=deneme_mi,
            sistem_gerekcesi=gerekce(c, deneme_mi))

    plan = [satir(c, pay.get(id(c), 0), False) for c in cekirdek]
    plan += [satir(c, dpay.get(id(c), 0), True) for c in deneme]
    plan.sort(key=lambda s: (-s['fayda'], s['yayinci'], s['reklam_modeli']))

    return dict(
        brief=brief, uyarilar=uyarilar, sektor_geri_cekildi=sektor_geri,
        filtre_aktif=filtre_aktif, uyari_esigi=uyari_esigi, satirlar=plan,
        toplam_dagitilan=sum(s['sistem_butce'] for s in plan),
        reklam_modeli_cesidi=len({s['reklam_modeli'] for s in plan}))


def gerekce(c, deneme_mi):
    """Sistemin bu satırı neden önerdiğini sade Türkçe anlatır (K6)."""
    parcalar = [f"puan {c['puan']} ({c['guven']})"]
    if c.get('teslim') is not None:
        parcalar.append(f"%{c['teslim']} yayınlanma")
    parcalar.append(f"önerilen birim {c['oner']} — {c['oner_kaynak']}, {c['oner_n']} gözlem")
    parcalar.append(f"kırılım: {c.get('kirilim_seviye', 'ana tür')}")
    if deneme_mi:
        parcalar.append("deneme payından: az tanıdığımız ama umut vaat eden yayıncı")
    return f"{c['yayinci']} · {c['reklam_modeli']} ({c['tip']}): " + "; ".join(parcalar) + "."


def ledger_kaydi(plan, kullanici):
    """Öneriyi karar defterine 'oneri' olarak yazar (seçim/sapma sonra eklenir)."""
    satirlar = []
    for s in plan['satirlar']:
        satirlar.append(dict(
            yayinci=s['yayinci'], grup=s['grup'], reklam_modeli=s['reklam_modeli'],
            ana_tur=s['ana_tur'], tip=s['tip'],
            sistem_butce=s['sistem_butce'], secilen_butce=s['sistem_butce'],
            sistem_birim=s['oner'], secilen_birim=s['oner'],
            sapma_butce=0.0, sapma_birim=0.0, deneme=s['deneme'],
            sebep='', sebep_gerekli=False))
    kayit = dict(
        zaman=datetime.datetime.now().isoformat(timespec='seconds'),
        kullanici=kullanici, tur='oneri',
        oneri_id=f"{plan['brief']['sektor_l2']}-{plan['brief']['amac']}-{plan['brief']['toplam_butce']}",
        brief=plan['brief'], satirlar=satirlar)
    return kararlar.kaydet(kayit)


def main():
    ap = argparse.ArgumentParser(description='Growth Hub öneri motoru')
    ap.add_argument('--sektor', required=True, help='Sektör L2 (ör. "İçecek")')
    ap.add_argument('--amac', required=True, help='Kampanya amacı (ör. "Gösterim almak")')
    ap.add_argument('--butce', required=True, type=float, help='Toplam bütçe (TL)')
    ap.add_argument('--format-cesidi', type=int, default=None, help='İstenen en az reklam modeli çeşidi')
    ap.add_argument('--karne', default=KARNE)
    ap.add_argument('--kullanici', default='sistem')
    ap.add_argument('--kaydet', action='store_true', help='Öneriyi karar defterine yaz')
    a = ap.parse_args()

    sz = Sozluk(SOZLUK)
    karne = json.load(open(a.karne, encoding='utf-8'))
    brief = dict(sektor_l2=a.sektor, amac=a.amac, toplam_butce=a.butce,
                 istenen_format_cesidi=a.format_cesidi)
    plan = oneri_uret(brief, karne, sz)

    print(f"\nBrief: {a.sektor} · {a.amac} · {a.butce:,.0f} ₺")
    for u in plan['uyarilar']:
        print(f"  ⚠ {u}")
    print(f"\n{'Yayıncı':16}{'Reklam modeli':18}{'Tip':6}{'Puan':>6}{'Fayda':>7}{'Bütçe ₺':>12}  Neden")
    for s in plan['satirlar']:
        et = ' [deneme]' if s['deneme'] else ''
        print(f"{s['yayinci']:16.16}{s['reklam_modeli']:18.18}{s['tip']:6.6}"
              f"{s['puan']:>6}{s['fayda']:>7}{s['sistem_butce']:>12,}{et}")
    print(f"\nToplam dağıtılan: {plan['toplam_dagitilan']:,} ₺ / {a.butce:,.0f} ₺"
          f"  ·  reklam modeli çeşidi: {plan['reklam_modeli_cesidi']}")
    if a.kaydet:
        ledger_kaydi(plan, a.kullanici)
        print("Öneri karar defterine yazıldı.")


if __name__ == '__main__':
    main()
