# -*- coding: utf-8 -*-
"""
T&G Growth Hub — Karar defteri (yalnız-ekleme).

Karar katmanının hafızası. Öneri geçmişi, seçilen plan, sapma ve sebep buraya yazılır;
puanlama YENİDEN HESAPLANMAZ (K3) — bu dosya sadece kararları saklar ve okur.

Biçim: veri/kararlar/kararlar.jsonl  (satır başına bir JSON kaydı, asla yeniden yazılmaz).

Kayıt şeması:
    zaman, kullanici, tur ("oneri"|"secim"), oneri_id, brief{...},
    satirlar: [ {yayinci, grup, reklam_modeli, ana_tur, tip,
                 sistem_butce, secilen_butce, sistem_birim, secilen_birim,
                 sapma_butce, sapma_birim, deneme, sebep, sebep_gerekli} ]

Kural (§1/§3): "sapabilir ama sebebini yazmak zorundadır" — eşik üstü sapması olup
sebebi boş bir 'secim' kaydı REDDEDİLİR.
"""
import json, os

KOK_DIZIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFTER = os.path.join(KOK_DIZIN, 'veri', 'kararlar', 'kararlar.jsonl')


def _yol(defter=None):
    return defter or DEFTER


def sebep_eksik(record):
    """Sebep gereken ama yazılmamış satırları döndürür (yalnız 'secim' için anlamlı)."""
    eksik = []
    for s in record.get('satirlar', []):
        if s.get('sebep_gerekli') and not str(s.get('sebep') or '').strip():
            eksik.append(s.get('yayinci'))
    return eksik


def kaydet(record, defter=None):
    """Bir kaydı deftere ekler (append). 'secim' kaydında sebepsiz sapma varsa reddeder."""
    if record.get('tur') not in ('oneri', 'secim'):
        raise ValueError("tur 'oneri' veya 'secim' olmalı")
    if record.get('tur') == 'secim':
        eksik = sebep_eksik(record)
        if eksik:
            raise ValueError('Sapma sebebi yazılmamış yayıncılar var: ' + ', '.join(map(str, eksik)))
    yol = _yol(defter)
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, 'a', encoding='utf-8') as fh:
        fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n')
    return record


def oku(defter=None):
    """Defterdeki tüm kayıtları (liste) döndürür. Defter yoksa boş liste."""
    yol = _yol(defter)
    if not os.path.exists(yol):
        return []
    kayitlar = []
    with open(yol, encoding='utf-8') as fh:
        for satir in fh:
            satir = satir.strip()
            if satir:
                kayitlar.append(json.loads(satir))
    return kayitlar
