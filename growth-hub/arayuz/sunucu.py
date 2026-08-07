# -*- coding: utf-8 -*-
"""
T&G Growth Hub — Yerel öneri arayüzü (Karar katmanı, canlı test).

Gerçek motora bağlıdır: karneyi puanlama/karne.json'dan okur (yeniden hesaplamaz — K3),
planı arayuz/oneri.py'daki oneri_uret ile üretir. Ortak arayüzü (arayuz/pages/index.html +
app.js) diskten sunar; MOTOR'u burada fetch tabanlı tanımlar (Pages sürümü aynı arayüzü
Pyodide ile besler). Sektör/amaç/platform menüleri karne + sozluk'tan gelir (K2).
Sapma + sebep akışını arayuz/kararlar.py defterine yazar; eşik üstü sapmada sebep boşsa
REDDEDER ("sapabilir ama sebebini yazmak zorundadır").

Çalıştırma (sıfır bağımlılık, sadece Python 3):
    python3 arayuz/sunucu.py            # -> http://localhost:8000
    python3 arayuz/sunucu.py --port 9000 --host 0.0.0.0
"""
import argparse, json, os, sys, datetime
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, 'sozluk'))
sys.path.insert(0, os.path.join(KOK, 'arayuz'))
from sozluk import Sozluk
import oneri
import kararlar

SOZLUK = os.path.join(KOK, 'sozluk', 'sozluk.xlsx')
KARNE = os.path.join(KOK, 'puanlama', 'karne.json')
PAGES = os.path.join(KOK, 'arayuz', 'pages')

# Yerel sürüm: MOTOR'u fetch ile sunucudaki gerçek motora bağlar (Pyodide yerine).
MOTOR_BOOT_JS = """
window.MOTOR = {
  meta: fetch('/api/meta').then(r => r.json()),
  filtreler: (s, a) => fetch('/api/filtreler?sektor=' + encodeURIComponent(s) + '&amac=' + encodeURIComponent(a)).then(r => r.json()),
  oneri: (brief) => fetch('/api/oneri', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(brief)}).then(r => r.json()),
};
window.MOTOR_READY = Promise.resolve();
"""


def karne_oku():
    return json.load(open(KARNE, encoding='utf-8')) if os.path.exists(KARNE) else None


def meta_uret(sz, karne):
    return dict(
        uyari_esigi=float(sz.p('uyari_esigi', 0.15)),
        min_format=int(sz.p('min_format_cesidi', 3)),
        kirilim=str(sz.p('karne_kirilim', 'ana tür')),
        karne_hucre=len(karne) if karne else 0,
        sektorler=sorted({c['s2'] for c in karne}) if karne else [],
        amaclar=sorted({t['amac'] for t in sz.turler.values() if t.get('amac')}),
    )


def secim_kaydi(sz, gonderi):
    """Seçilen planı 'secim' olarak deftere yazar. sebep_gerekli SUNUCUDA (uyari_esigi
    sözlükten) hesaplanır — istemci atlayamaz. kararlar.kaydet eşik üstü sapmada boş sebebi reddeder."""
    esik = float(sz.p('uyari_esigi', 0.15))
    satirlar = []
    for s in gonderi.get('satirlar', []):
        sistem = float(s.get('sistem_butce') or 0)
        secilen = float(s.get('secilen_butce') or 0)
        sapma = (abs(secilen - sistem) / sistem) if sistem else (1.0 if secilen else 0.0)
        satirlar.append(dict(
            yayinci=s.get('yayinci'), grup=s.get('grup'),
            reklam_modeli=s.get('reklam_modeli'), ana_tur=s.get('ana_tur'), tip=s.get('tip'),
            sistem_butce=sistem, secilen_butce=secilen,
            sistem_birim=s.get('oner'), secilen_birim=s.get('oner'),
            sapma_butce=round(secilen - sistem, 2), sapma_birim=0.0,
            deneme=bool(s.get('deneme')),
            sebep=str(s.get('sebep') or '').strip(),
            sebep_gerekli=sapma > esik))
    kayit = dict(
        zaman=datetime.datetime.now().isoformat(timespec='seconds'),
        kullanici=gonderi.get('kullanici', 'arayuz'), tur='secim',
        oneri_id=gonderi.get('oneri_id', ''),
        brief=gonderi.get('brief', {}), satirlar=satirlar)
    kararlar.kaydet(kayit)
    return kayit


class Handler(BaseHTTPRequestHandler):
    def _gonder(self, kod, govde, tip):
        c = govde.encode('utf-8') if isinstance(govde, str) else govde
        self.send_response(kod)
        self.send_header('Content-Type', tip)
        self.send_header('Content-Length', str(len(c)))
        self.end_headers()
        self.wfile.write(c)

    def _json(self, kod, govde):
        self._gonder(kod, json.dumps(govde, ensure_ascii=False), 'application/json; charset=utf-8')

    def _dosya(self, ad, tip):
        yol = os.path.join(PAGES, ad)
        if not os.path.exists(yol):
            return self._json(404, dict(hata=f'{ad} yok'))
        with open(yol, encoding='utf-8') as fh:
            self._gonder(200, fh.read(), tip)

    def _govde(self):
        n = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(n) or b'{}')

    def log_message(self, *a):
        pass

    def do_GET(self):
        yol = urlparse(self.path)
        p = yol.path
        if p == '/':
            return self._dosya('index.html', 'text/html; charset=utf-8')
        if p == '/app.js':
            return self._dosya('app.js', 'application/javascript; charset=utf-8')
        if p == '/supabase-config.js':
            return self._dosya('supabase-config.js', 'application/javascript; charset=utf-8')
        if p == '/motor-boot.js':
            return self._gonder(200, MOTOR_BOOT_JS, 'application/javascript; charset=utf-8')
        sz = Sozluk(SOZLUK)
        karne = karne_oku()
        if p == '/api/meta':
            if karne is None:
                return self._json(200, dict(hata='karne.json yok — önce puanlama/skor.py çalıştırın.'))
            return self._json(200, meta_uret(sz, karne))
        if p == '/api/filtreler':
            q = parse_qs(yol.query)
            sektor = (q.get('sektor') or [''])[0]
            amac = (q.get('amac') or [''])[0]
            if karne is None:
                return self._json(400, dict(hata='karne.json yok'))
            brief = dict(sektor_l2=sektor, amac=amac, toplam_butce=1, istenen_format_cesidi=None)
            return self._json(200, oneri.filtre_secenekleri(brief, karne, sz))
        if p == '/api/defter':
            return self._json(200, dict(kayitlar=kararlar.oku()))
        return self._json(404, dict(hata='bulunamadı'))

    def do_POST(self):
        p = urlparse(self.path).path
        sz = Sozluk(SOZLUK)
        karne = karne_oku()
        try:
            g = self._govde()
        except Exception as e:
            return self._json(400, dict(hata=f'geçersiz istek: {e}'))
        if p == '/api/oneri':
            if karne is None:
                return self._json(400, dict(hata='karne.json yok — önce puanlama/skor.py çalıştırın.'))
            try:
                brief = dict(
                    sektor_l2=g['sektor_l2'], amac=g['amac'],
                    toplam_butce=float(g['toplam_butce']),
                    istenen_format_cesidi=(int(g['istenen_format_cesidi']) if g.get('istenen_format_cesidi') else None),
                    yayinci_filtre=g.get('yayinci_filtre'),
                    reklam_modeli_filtre=g.get('reklam_modeli_filtre'))
                return self._json(200, oneri.oneri_uret(brief, karne, sz))
            except Exception as e:
                return self._json(400, dict(hata=f'öneri üretilemedi: {e}'))
        if p == '/api/karar':
            try:
                kayit = secim_kaydi(sz, g)
                return self._json(200, dict(ok=True, yazildi=len(kayit['satirlar'])))
            except ValueError as e:
                return self._json(422, dict(hata=str(e)))
            except Exception as e:
                return self._json(400, dict(hata=f'kaydedilemedi: {e}'))
        return self._json(404, dict(hata='bulunamadı'))


def main():
    ap = argparse.ArgumentParser(description='Growth Hub yerel öneri arayüzü')
    ap.add_argument('--port', type=int, default=8000)
    ap.add_argument('--host', default='127.0.0.1')
    a = ap.parse_args()
    if karne_oku() is None:
        print('UYARI: puanlama/karne.json yok. Önce: cd puanlama && python3 skor.py /tmp/donusum.json .')
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f'Growth Hub arayüzü:  http://{a.host}:{a.port}   (durdurmak için Ctrl+C)')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\nkapatıldı.')


if __name__ == '__main__':
    main()
