# -*- coding: utf-8 -*-
"""
T&G Growth Hub — Yerel öneri arayüzü (Karar katmanı, canlı test).

Mockup'ın aksine bu sunucu GERÇEK motora bağlıdır:
  * Karneyi puanlama/karne.json'dan okur (yeniden hesaplamaz — K3).
  * Brief için planı arayuz/oneri.py'daki oneri_uret ile üretir (tek hesap yeri — K3).
  * Sektör/amaç menülerini karne + sozluk'tan doldurur (kodda gömülü liste yok — K2).
  * Sapma + sebep akışını arayuz/kararlar.py defterine yazar; eşik üstü sapmada
    sebep boşsa REDDEDER ("sapabilir ama sebebini yazmak zorundadır").

Tarayıcıdaki JS hiçbir sayıyı yeniden hesaplamaz; yalnızca Python'un döndürdüğünü çizer.

Çalıştırma (sıfır bağımlılık, sadece Python 3):
    python3 arayuz/sunucu.py            # -> http://localhost:8000
    python3 arayuz/sunucu.py --port 9000 --host 0.0.0.0
"""
import argparse, json, os, sys, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, 'sozluk'))
sys.path.insert(0, os.path.join(KOK, 'arayuz'))
from sozluk import Sozluk
import oneri
import kararlar

SOZLUK = os.path.join(KOK, 'sozluk', 'sozluk.xlsx')
KARNE = os.path.join(KOK, 'puanlama', 'karne.json')


def karne_oku():
    if not os.path.exists(KARNE):
        return None
    return json.load(open(KARNE, encoding='utf-8'))


def meta_uret(sz, karne):
    """Form menüleri: yalnızca veri/sözlükte OLAN sektör ve amaçlar (K2, dürüst kapsam)."""
    sektorler = sorted({c['s2'] for c in karne}) if karne else []
    amaclar = sorted({t['amac'] for t in sz.turler.values() if t.get('amac')})
    return dict(
        sektorler=sektorler,
        amaclar=amaclar,
        uyari_esigi=float(sz.p('uyari_esigi', 0.15)),
        min_format=int(sz.p('min_format_cesidi', 3)),
        karne_hucre=len(karne) if karne else 0,
        kirilim=str(sz.p('karne_kirilim', 'ana tür')),
    )


def secim_kaydi(sz, gonderi):
    """Kullanıcının seçtiği planı 'secim' olarak deftere yazar.

    sebep_gerekli SUNUCUDA hesaplanır (uyari_esigi sözlükten) — istemci bunu
    atlayamaz. kararlar.kaydet eşik üstü sapmada sebep boşsa reddeder.
    """
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
    kararlar.kaydet(kayit)   # ValueError -> sebepsiz sapma
    return kayit


class Handler(BaseHTTPRequestHandler):
    def _json(self, kod, govde):
        c = json.dumps(govde, ensure_ascii=False).encode('utf-8')
        self.send_response(kod)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(c)))
        self.end_headers()
        self.wfile.write(c)

    def _html(self, govde):
        c = govde.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(c)))
        self.end_headers()
        self.wfile.write(c)

    def _govde(self):
        n = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(n) or b'{}')

    def log_message(self, *a):
        pass  # sessiz

    def do_GET(self):
        yol = self.path.split('?')[0]
        if yol == '/':
            return self._html(SAYFA)
        sz = Sozluk(SOZLUK)
        karne = karne_oku()
        if yol == '/api/meta':
            if karne is None:
                return self._json(200, dict(hata='karne.json yok — önce puanlama/skor.py çalıştırın.'))
            return self._json(200, meta_uret(sz, karne))
        if yol == '/api/defter':
            return self._json(200, dict(kayitlar=kararlar.oku()))
        return self._json(404, dict(hata='bulunamadı'))

    def do_POST(self):
        yol = self.path.split('?')[0]
        sz = Sozluk(SOZLUK)
        karne = karne_oku()
        try:
            g = self._govde()
        except Exception as e:
            return self._json(400, dict(hata=f'geçersiz istek: {e}'))
        if yol == '/api/oneri':
            if karne is None:
                return self._json(400, dict(hata='karne.json yok — önce puanlama/skor.py çalıştırın.'))
            try:
                brief = dict(
                    sektor_l2=g['sektor'], amac=g['amac'],
                    toplam_butce=float(g['butce']),
                    istenen_format_cesidi=(int(g['format_cesidi']) if g.get('format_cesidi') else None))
                plan = oneri.oneri_uret(brief, karne, sz)
                return self._json(200, plan)
            except Exception as e:
                return self._json(400, dict(hata=f'öneri üretilemedi: {e}'))
        if yol == '/api/karar':
            try:
                kayit = secim_kaydi(sz, g)
                return self._json(200, dict(ok=True, yazildi=len(kayit['satirlar'])))
            except ValueError as e:
                return self._json(422, dict(hata=str(e)))
            except Exception as e:
                return self._json(400, dict(hata=f'kaydedilemedi: {e}'))
        return self._json(404, dict(hata='bulunamadı'))


SAYFA = r"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Growth Hub — Öneri</title>
<style>
:root{--ink:#1a1a1a;--paper:#faf8f4;--line:#e2ddd3;--accent:#c8543a;--iyi:#3a7d5a;--uyari:#b8862a;--kart:#fff}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
header{background:var(--ink);color:var(--paper);padding:16px 28px}
header b{font-size:18px}header span{opacity:.7;font-size:12px;margin-left:12px}
.wrap{max-width:1140px;margin:0 auto;padding:24px 28px}
.kart{background:var(--kart);border:1px solid var(--line);border-radius:10px;padding:20px 22px;margin-bottom:22px}
.form{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-end}
.alan{display:flex;flex-direction:column;gap:5px}
.alan label{font-size:12px;font-weight:600;color:#555}
select,input{font:inherit;padding:9px 11px;border:1px solid var(--line);border-radius:7px;background:#fff;min-width:150px}
input[type=number]{min-width:150px}
button{font:inherit;font-weight:600;padding:10px 20px;border:0;border-radius:7px;background:var(--accent);color:#fff;cursor:pointer}
button.ikincil{background:#fff;color:var(--ink);border:1px solid var(--line)}
button:disabled{opacity:.5;cursor:not-allowed}
.uyari{background:#fdf6e6;border:1px solid #e6d9b0;color:#7a5a10;padding:9px 13px;border-radius:7px;margin:6px 0;font-size:13.5px}
table{width:100%;border-collapse:collapse;margin-top:8px;font-size:13.5px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:11.5px;text-transform:uppercase;letter-spacing:.04em;color:#777}
td.sag,th.sag{text-align:right}
.rozet{display:inline-block;font-size:11px;padding:2px 7px;border-radius:20px;background:#eee;color:#555}
.rozet.deneme{background:#efe6fb;color:#6b3fa0}
.cubuk{height:6px;border-radius:4px;background:#eee;position:relative;margin-top:4px;overflow:hidden}
.cubuk>i{position:absolute;top:0;bottom:0;background:var(--iyi);border-radius:4px}
.emin{font-size:11px;color:#888}
.neden{color:#555;font-size:12.5px}
.butce-in{width:120px;text-align:right}
.sebep-in{width:100%;margin-top:5px;display:none}
.sebep-in.gerek{display:block;border-color:var(--accent)}
.toplam{font-weight:700;font-size:15px}
.iyi{color:var(--iyi)}.kotu{color:var(--accent)}
.mini{font-size:12px;color:#888}
.durum{padding:9px 13px;border-radius:7px;font-size:13.5px;margin-top:10px}
.durum.ok{background:#eaf5ee;color:#215a3a}
.durum.hata{background:#fbecea;color:#8a2f22}
.bos{color:#999;padding:22px;text-align:center}
</style></head><body>
<header><b>Growth Hub</b><span>Mecra önerisi — canlı motor (karne.json + oneri.py)</span></header>
<div class="wrap">

  <div class="kart">
    <div class="form">
      <div class="alan"><label>Sektör</label><select id="sektor"></select></div>
      <div class="alan"><label>Amaç</label><select id="amac"></select></div>
      <div class="alan"><label>Bütçe (₺)</label><input id="butce" type="number" min="0" step="10000" value="4200000"></div>
      <div class="alan"><label>En az reklam modeli çeşidi</label><input id="cesit" type="number" min="1" placeholder="varsayılan"></div>
      <button id="oner">Öneri üret</button>
    </div>
    <div id="meta" class="mini" style="margin-top:12px"></div>
  </div>

  <div id="uyarilar"></div>

  <div class="kart" id="sonuc-kart" style="display:none">
    <div id="baslik" style="font-weight:700;margin-bottom:4px"></div>
    <div id="ozet" class="mini"></div>
    <div id="tablo-sar"></div>
    <div style="margin-top:16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap">
      <button id="kaydet" class="ikincil">Seçilen planı deftere yaz</button>
      <span class="mini">Sistem bütçesinden %<span id="esik"></span>'ten fazla sapan satırda sebep zorunlu.</span>
    </div>
    <div id="durum"></div>
  </div>

</div>
<script>
const $=s=>document.querySelector(s);
let META=null, PLAN=null;

async function jget(u){const r=await fetch(u);return r.json();}
async function jpost(u,b){const r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});return {kod:r.status, veri:await r.json()};}
const tl=n=>Number(n||0).toLocaleString('tr-TR');

async function basla(){
  META=await jget('/api/meta');
  if(META.hata){$('#meta').innerHTML='<span class="kotu">'+META.hata+'</span>';return;}
  $('#sektor').innerHTML=META.sektorler.map(s=>`<option>${s}</option>`).join('');
  $('#amac').innerHTML=META.amaclar.map(s=>`<option>${s}</option>`).join('');
  $('#cesit').placeholder='varsayılan '+META.min_format;
  $('#esik').textContent=Math.round(META.uyari_esigi*100);
  $('#meta').textContent=`Karne: ${META.karne_hucre} hücre · kırılım: ${META.kirilim} · uyarı eşiği %${Math.round(META.uyari_esigi*100)}`;
}

function cubuk(puan,aralik){
  const alt=Math.max(0,puan-aralik), ust=Math.min(200,puan+aralik), gen=(ust-alt)/2;
  return `<div>${puan} <span class="emin">± ${aralik}</span></div>
    <div class="cubuk" title="ne kadar emin olduğumuz"><i style="left:${alt/2}%;width:${gen}%"></i></div>`;
}

function ciz(p){
  PLAN=p;
  $('#uyarilar').innerHTML=(p.uyarilar||[]).map(u=>`<div class="uyari">⚠ ${u}</div>`).join('');
  $('#sonuc-kart').style.display='block';
  const b=p.brief;
  $('#baslik').textContent=`${b.sektor_l2} · ${b.amac} · ${tl(b.toplam_butce)} ₺`;
  $('#ozet').textContent=`Dağıtılan ${tl(p.toplam_dagitilan)} ₺ / ${tl(b.toplam_butce)} ₺ · reklam modeli çeşidi ${p.reklam_modeli_cesidi}`;
  if(!p.satirlar.length){$('#tablo-sar').innerHTML='<div class="bos">Bu brief için uygun hücre bulunamadı.</div>';return;}
  let h=`<table><thead><tr>
    <th>Yayıncı</th><th>Reklam modeli</th><th>Tip</th><th>Puan / ne kadar emin</th>
    <th class="sag">Fayda</th><th class="sag">Önerilen birim</th>
    <th class="sag">Sistem bütçesi</th><th class="sag">Senin bütçen</th></tr></thead><tbody>`;
  p.satirlar.forEach((s,i)=>{
    h+=`<tr>
      <td><b>${s.yayinci}</b><div class="mini">${s.grup}</div></td>
      <td>${s.reklam_modeli} ${s.deneme?'<span class="rozet deneme">deneme</span>':''}</td>
      <td>${s.tip}</td>
      <td>${cubuk(s.puan,s.aralik)}<div class="mini">${s.guven}</div></td>
      <td class="sag">${s.fayda}</td>
      <td class="sag">${tl(s.oner)}<div class="mini">${s.oner_kaynak}, ${s.oner_n}</div></td>
      <td class="sag">${tl(s.sistem_butce)} ₺</td>
      <td class="sag">
        <input class="butce-in" type="number" data-i="${i}" value="${s.sistem_butce}">
        <input class="sebep-in" data-i="${i}" placeholder="sapma sebebi (zorunlu)">
      </td></tr>
      <tr><td colspan="8" class="neden">↳ ${s.sistem_gerekcesi}</td></tr>`;
  });
  h+='</tbody></table>';
  $('#tablo-sar').innerHTML=h;
  $('#durum').innerHTML='';
  document.querySelectorAll('.butce-in').forEach(inp=>inp.addEventListener('input',sapmaKontrol));
  sapmaKontrol();
}

function sapmaKontrol(){
  const esik=META.uyari_esigi;
  document.querySelectorAll('.butce-in').forEach(inp=>{
    const i=+inp.dataset.i, sis=PLAN.satirlar[i].sistem_butce;
    const sec=Number(inp.value||0);
    const sapma=sis?Math.abs(sec-sis)/sis:(sec?1:0);
    const seb=document.querySelector(`.sebep-in[data-i="${i}"]`);
    seb.classList.toggle('gerek', sapma>esik);
  });
}

async function oner(){
  $('#oner').disabled=true;$('#oner').textContent='Hesaplanıyor…';
  const r=await jpost('/api/oneri',{sektor:$('#sektor').value,amac:$('#amac').value,
    butce:$('#butce').value, format_cesidi:$('#cesit').value});
  $('#oner').disabled=false;$('#oner').textContent='Öneri üret';
  if(r.kod!==200){$('#uyarilar').innerHTML=`<div class="uyari kotu">✕ ${r.veri.hata}</div>`;return;}
  ciz(r.veri);
}

async function kaydet(){
  const satirlar=PLAN.satirlar.map((s,i)=>({...s,
    secilen_butce:Number(document.querySelector(`.butce-in[data-i="${i}"]`).value||0),
    sebep:document.querySelector(`.sebep-in[data-i="${i}"]`).value}));
  const r=await jpost('/api/karar',{brief:PLAN.brief,
    oneri_id:`${PLAN.brief.sektor_l2}-${PLAN.brief.amac}-${PLAN.brief.toplam_butce}`,satirlar});
  const d=$('#durum');
  if(r.kod===200){d.className='durum ok';d.textContent=`✓ Deftere yazıldı (${r.veri.yazildi} satır). Karar defteri: veri/kararlar/kararlar.jsonl`;}
  else{d.className='durum hata';d.textContent=`✕ ${r.veri.hata}`;}
}

$('#oner').addEventListener('click',oner);
$('#kaydet').addEventListener('click',kaydet);
basla();
</script>
</body></html>"""


def main():
    ap = argparse.ArgumentParser(description='Growth Hub yerel öneri arayüzü')
    ap.add_argument('--port', type=int, default=8000)
    ap.add_argument('--host', default='127.0.0.1')
    a = ap.parse_args()
    if karne_oku() is None:
        print('UYARI: puanlama/karne.json yok. Önce şunu çalıştırın:')
        print('  cd puanlama && python3 skor.py /tmp/donusum.json .')
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f'Growth Hub arayüzü:  http://{a.host}:{a.port}   (durdurmak için Ctrl+C)')
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\nkapatıldı.')


if __name__ == '__main__':
    main()
