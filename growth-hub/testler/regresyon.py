# -*- coding: utf-8 -*-
"""
T&G Growth Hub — Bölüm 5 regresyon testleri (çalıştırılabilir).

    python3 testler/regresyon.py

CLAUDE.md §5'teki testleri koda döker. Her değişiklikten sonra çalıştırın; hepsi GEÇTİ olmalı.
Not: Şablon formül kontrolü (C26) için LibreOffice recalc.py bu ortamda kilitleniyor;
onun yerine per-kampanya gerçekleşen toplamı (donusum.json) referansla karşılaştırılır.
Tam C26 formül doğrulaması ayrıca `formulas` python kütüphanesiyle yapılabilir.
"""
import sys, os, io, json, datetime, importlib.util, collections, contextlib

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for alt in ('sozluk', 'donusturucu', 'puanlama', 'arayuz'):
    sys.path.insert(0, os.path.join(KOK, alt))
from sozluk import Sozluk, norm
import donustur
import oneri
import kararlar

SOZLUK = os.path.join(KOK, 'sozluk', 'sozluk.xlsx')
HAM = os.path.join(KOK, 'veri', 'ham')
KARNE = os.path.join(KOK, 'puanlama', 'karne.json')
BUGUN = datetime.date(2026, 8, 6)
REF_TOPLAM, REF_SATIR, REF_KAMPANYA = 25_676_102, 132, 8

_skor_spec = importlib.util.spec_from_file_location('skor', os.path.join(KOK, 'puanlama', 'skor.py'))
skor = importlib.util.module_from_spec(_skor_spec); sys.modules['skor'] = skor; _skor_spec.loader.exec_module(skor)

sonuclar = []
def kontrol(ad, kosul, detay=''):
    sonuclar.append(kosul)
    print(f"  [{'GEÇTİ' if kosul else 'KALDI'}] {ad}" + (f"  — {detay}" if detay else ''))


def puanla(D, sz, kirilim):
    sz.parametreler[norm('karne_kirilim')] = kirilim
    return skor.puanla(skor.satirlari_hazirla(D, BUGUN), sz, bugun=BUGUN)


def main():
    sz = Sozluk(SOZLUK)
    with contextlib.redirect_stdout(io.StringIO()):
        D = donustur.calistir(HAM, SOZLUK)

    # T5.5 sözlük eksikleri + T-B reklam_modeli additive
    print("\n1) Dönüştürücü + sözlük eksikleri")
    satir = sum(len(k['satirlar']) for k in D)
    kontrol('132 satır / 8 kampanya', satir == REF_SATIR and len(D) == REF_KAMPANYA, f'{satir} satır, {len(D)} kampanya')
    kontrol('SÖZLÜKTE YOK yok', not any(sz.eksikler[k] for k in sz.eksikler))
    kontrol('her satırda reklam_modeli dolu',
            all(x.get('reklam_modeli') for k in D for x in k['satirlar']))
    toplam = sum((x['ger_bedel'] or 0) for k in D for x in k['satirlar'])
    kontrol('gerçekleşen toplam ≈ referans', abs(round(toplam) - REF_TOPLAM) <= 1, f'{toplam:,.0f} ₺')

    # T5.1/backward-compat: kapalı = bugün
    print("\n2) Kırılım kapalı (ana tür) = bugünkü davranış")
    kapali = puanla(D, sz, 'ana tür')
    kontrol('92 karne hücresi', len(kapali) == 92, f'{len(kapali)} hücre')
    kontrol('rm ana tür’e çöküyor (reklam_modeli==tur)', all(c['reklam_modeli'] == c['tur'] for c in kapali))
    kontrol('güven eşiğini geçen 1/92', sum(1 for c in kapali if c['n'] >= int(sz.p('guven_esigi'))) == 1)
    # tarihten bağımsız alanlarda commit’li karne ile birebir
    if os.path.exists(KARNE):
        ref = {(x['s2'], x['grup'], x['yayinci'], x['tur'], x['tip']): x for x in json.load(open(KARNE, encoding='utf-8'))}
        yeni = {(x['s2'], x['grup'], x['yayinci'], x['tur'], x['tip']): x for x in kapali}
        di = ['n', 'aralik', 'teslim', 'harcama', 'kampanya', 'oner', 'oner_kaynak', 'oner_n', 'ornek_tur', 'guven', 'havuz']
        parite = set(ref) == set(yeni) and all(ref[k][f] == yeni[k].get(f) for k in ref for f in di)
        kontrol('tarih-bağımsız alanlar commit’li karne ile birebir', parite)

    # T5.2: kırılım açık = dürüst incelme
    print("\n3) Kırılım açık (reklam modeli) = dürüst incelme")
    acik = puanla(D, sz, 'reklam modeli')
    ebeveyn = {(c['s2'], c['grup'], c['yayinci'], c['tur'], c['tip']): c for c in kapali}
    guv = int(sz.p('guven_esigi'))
    kontrol('hücre sayısı > 92', len(acik) > 92, f'{len(acik)} hücre')
    kontrol('çocuk n ≤ ebeveyn n', all(c['n'] <= ebeveyn[(c['s2'], c['grup'], c['yayinci'], c['tur'], c['tip'])]['n'] for c in acik))
    kontrol('çocuk aralık ≥ ebeveyn aralık', all(c['aralik'] >= ebeveyn[(c['s2'], c['grup'], c['yayinci'], c['tur'], c['tip'])]['aralik'] for c in acik))
    kontrol('az veri "kendi verisi" demiyor', all(not (c['n'] < guv and c['guven'] == 'kendi verisi') for c in acik))

    # T5.4: parametre bağı
    print("\n4) Parametre bağı (zaman_yari_omru_ay 18 → 3)")
    a = {(x['s2'], x['grup'], x['yayinci'], x['tur'], x['tip']): x['puan'] for x in puanla(D, sz, 'ana tür')}
    sz.parametreler[norm('zaman_yari_omru_ay')] = 3
    b = {(x['s2'], x['grup'], x['yayinci'], x['tur'], x['tip']): x['puan'] for x in puanla(D, sz, 'ana tür')}
    degisen = sum(1 for k in a if a[k] != b[k])
    kontrol('puanların bir kısmı değişiyor', degisen > 0, f'{degisen}/92 hücre')
    sz.parametreler[norm('zaman_yari_omru_ay')] = 18

    # T5.3: öneri tavanları
    print("\n5) Öneri motoru tavanları")
    fine = puanla(D, sz, 'reklam modeli')
    tavan = float(sz.p('tek_grup_tavani')); min_b = float(sz.p('min_yayinci_butcesi')); min_f = int(sz.p('min_format_cesidi'))
    briefler = [('İçecek', 'Gösterim almak', 4200000), ('Hazır Yiyecek', 'Video izletmek', 3000000),
                ('Ulaşım Uygulaması', 'Video izletmek', 5000000), ('Hazır Yiyecek', 'Siteye trafik', 1500000)]
    hepsi = True
    for s, am, bu in briefler:
        p = oneri.oneri_uret(dict(sektor_l2=s, amac=am, toplam_butce=bu, istenen_format_cesidi=None), fine, sz)
        rows = p['satirlar']; tot = sum(r['sistem_butce'] for r in rows)
        gtop = collections.defaultdict(float)
        for r in rows: gtop[r['grup']] += r['sistem_butce']
        maxg = (max(gtop.values()) / bu) if gtop else 0
        cesit = len({r['reklam_modeli'] for r in rows})
        cesit_uyari = any('çeşidine ulaşılamadı' in u for u in p['uyarilar'])
        ok = (tot <= bu + 1 and maxg <= tavan + 0.011 and
              all(r['sistem_butce'] >= min_b - 1 or r['deneme'] for r in rows) and
              (cesit >= min_f or cesit_uyari))
        hepsi = hepsi and ok
    kontrol('Σ≤bütçe, grup tavanı, min bütçe, format çeşidi (4 brief)', hepsi)

    # T-E: karar defteri
    print("\n6) Karar defteri")
    T = '/tmp/_regresyon_kararlar.jsonl'
    if os.path.exists(T): os.remove(T)
    rec = dict(zaman='t', kullanici='z', tur='oneri', oneri_id='x', brief={},
               satirlar=[dict(yayinci='X', sistem_butce=1, secilen_butce=1, sebep='', sebep_gerekli=False)])
    kararlar.kaydet(rec, defter=T); b1 = os.path.getsize(T)
    kararlar.kaydet(rec, defter=T); b2 = os.path.getsize(T)
    kontrol('yalnız-ekleme + determinizm', len(kararlar.oku(T)) == 2 and b2 == 2 * b1)
    red = False
    try:
        kararlar.kaydet(dict(tur='secim', satirlar=[dict(yayinci='Meta', sebep_gerekli=True, sebep='')]), defter=T)
    except ValueError:
        red = True
    kontrol('sebepsiz sapma reddedilir', red)
    os.remove(T)

    print(f"\n{'='*48}\nSONUÇ: {sum(sonuclar)}/{len(sonuclar)} test geçti")
    return 0 if all(sonuclar) else 1


if __name__ == '__main__':
    sys.exit(main())
