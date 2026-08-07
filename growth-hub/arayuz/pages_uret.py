# -*- coding: utf-8 -*-
"""
T&G Growth Hub — GitHub Pages statik veri üreticisi.

GERÇEK motoru (arayuz/oneri.py) bir brief ızgarası üzerinde çalıştırır ve sonuçları
statik bir JS dosyasına (arayuz/pages/veri.js) döker. Pages sayfası bu dosyayı okur;
tarayıcıda hiçbir sayı yeniden hesaplanmaz (K3). Menüler ve eşikler karne + sozluk'tan
gelir (K2). Bütçe kademelidir; kademeler sozluk'tan (pages_butce_kademeleri) okunur,
yoksa makul bir varsayılan kullanılır.

Çalıştırma (yerelde ya da CI'da):
    python3 arayuz/pages_uret.py
    -> arayuz/pages/veri.js  (window.GH_VERI = {...})
"""
import json, os, sys, datetime

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, 'sozluk'))
sys.path.insert(0, os.path.join(KOK, 'arayuz'))
from sozluk import Sozluk
import oneri

SOZLUK = os.path.join(KOK, 'sozluk', 'sozluk.xlsx')
KARNE = os.path.join(KOK, 'puanlama', 'karne.json')
CIKTI = os.path.join(KOK, 'arayuz', 'pages', 'veri.js')

VARSAYILAN_KADEMELER = [500000, 1000000, 2000000, 3000000, 5000000, 10000000]


def butce_kademeleri(sz):
    ham = sz.p('pages_butce_kademeleri', None)
    if ham:
        try:
            return sorted({int(float(x)) for x in str(ham).replace(';', ',').split(',') if x.strip()})
        except ValueError:
            pass
    return VARSAYILAN_KADEMELER


def anahtar(sektor, amac, butce):
    return f"{sektor}||{amac}||{int(butce)}"


def uret():
    sz = Sozluk(SOZLUK)
    karne = json.load(open(KARNE, encoding='utf-8'))

    sektorler = sorted({c['s2'] for c in karne})
    amaclar = sorted({t['amac'] for t in sz.turler.values() if t.get('amac')})
    kademeler = butce_kademeleri(sz)

    planlar = {}
    for s in sektorler:
        for a in amaclar:
            for b in kademeler:
                brief = dict(sektor_l2=s, amac=a, toplam_butce=float(b), istenen_format_cesidi=None)
                planlar[anahtar(s, a, b)] = oneri.oneri_uret(brief, karne, sz)

    veri = dict(
        meta=dict(
            uretim_zamani=datetime.datetime.now().isoformat(timespec='seconds'),
            uyari_esigi=float(sz.p('uyari_esigi', 0.15)),
            min_format=int(sz.p('min_format_cesidi', 3)),
            kirilim=str(sz.p('karne_kirilim', 'ana tür')),
            karne_hucre=len(karne),
            sektorler=sektorler, amaclar=amaclar, butce_kademeleri=kademeler,
        ),
        planlar=planlar,
    )
    os.makedirs(os.path.dirname(CIKTI), exist_ok=True)
    with open(CIKTI, 'w', encoding='utf-8') as fh:
        fh.write('window.GH_VERI = ')
        json.dump(veri, fh, ensure_ascii=False, separators=(',', ':'))
        fh.write(';\n')
    print(f'{CIKTI} yazıldı: {len(planlar)} plan '
          f'({len(sektorler)} sektör × {len(amaclar)} amaç × {len(kademeler)} bütçe kademesi)')


if __name__ == '__main__':
    uret()
