# -*- coding: utf-8 -*-
"""
T&G Growth Hub — GitHub Pages varlık hazırlayıcı.

Pages sürümü gerçek motoru tarayıcıda (Pyodide) çalıştırır. Bu betik, motorun ihtiyaç
duyduğu Python dosyalarını ve veriyi Pages klasörüne (arayuz/pages/motor/) kopyalar; böylece
tarayıcı bunları çekip oneri.py'ı aynen koşturabilir (K3 — mantık tek yerde). Karne ya da
sözlük değişince GitHub Action bu betiği çalıştırıp motor/ içeriğini tazeler.

Çalıştırma:
    python3 arayuz/pages_uret.py     -> arayuz/pages/motor/{oneri.py,sozluk.py,kararlar.py,sozluk.xlsx,karne.json}
"""
import os, shutil

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOTOR = os.path.join(KOK, 'arayuz', 'pages', 'motor')

# (kaynak, hedef ad) — motorun tarayıcıda import edeceği dosyalar + veri
VARLIKLAR = [
    (os.path.join(KOK, 'arayuz', 'oneri.py'), 'oneri.py'),
    (os.path.join(KOK, 'arayuz', 'kararlar.py'), 'kararlar.py'),
    (os.path.join(KOK, 'arayuz', 'disa_aktar.py'), 'disa_aktar.py'),
    (os.path.join(KOK, 'sozluk', 'sozluk.py'), 'sozluk.py'),
    (os.path.join(KOK, 'sozluk', 'sozluk.xlsx'), 'sozluk.xlsx'),
    (os.path.join(KOK, 'puanlama', 'karne.json'), 'karne.json'),
]


def uret():
    os.makedirs(MOTOR, exist_ok=True)
    for kaynak, ad in VARLIKLAR:
        if not os.path.exists(kaynak):
            raise FileNotFoundError(f'gerekli dosya yok: {kaynak}')
        shutil.copyfile(kaynak, os.path.join(MOTOR, ad))
    print(f'{MOTOR} güncellendi: ' + ', '.join(ad for _, ad in VARLIKLAR))


if __name__ == '__main__':
    uret()
