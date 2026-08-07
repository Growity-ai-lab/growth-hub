/* Growth Hub — Pages MOTOR sağlayıcısı (Pyodide).
 *
 * Gerçek oneri.py'ı tarayıcıda (WASM) çalıştırır — hiçbir mantık yeniden yazılmaz (K3).
 * motor/ altındaki Python dosyalarını ve veriyi (karne.json, sozluk.xlsx) çeker, Pyodide
 * dosya sistemine yazar, oneri.py'ı içe aktarır ve MOTOR arayüzünü tanımlar.
 * Yerel sunucu (sunucu.py) bu dosyanın yerine fetch tabanlı bir MOTOR sunar.
 */
const PYODIDE_SURUM = 'v0.26.2';
const MOTOR_DOSYALARI = ['oneri.py', 'sozluk.py', 'kararlar.py'];   // /app'e yazılır
const VERI_METIN = ['karne.json'];                                  // metin
const VERI_IKILI = ['sozluk.xlsx'];                                 // ikili

window.MOTOR = {};
window.MOTOR_READY = (async () => {
  // 1) Pyodide çalışma zamanı
  const s = document.createElement('script');
  s.src = `https://cdn.jsdelivr.net/pyodide/${PYODIDE_SURUM}/full/pyodide.js`;
  await new Promise((ok, hata) => { s.onload = ok; s.onerror = () => hata(new Error('Pyodide indirilemedi')); document.head.appendChild(s); });
  const pyodide = await loadPyodide({ indexURL: `https://cdn.jsdelivr.net/pyodide/${PYODIDE_SURUM}/full/` });

  // 2) sözlük okuması için openpyxl (saf Python)
  await pyodide.loadPackage('micropip');
  await pyodide.runPythonAsync(`import micropip\nawait micropip.install('openpyxl')`);

  // 3) motor dosyaları + veri -> /app
  pyodide.FS.mkdirTree('/app');
  for (const f of [...MOTOR_DOSYALARI, ...VERI_METIN]) {
    const t = await (await fetch('motor/' + f)).text();
    pyodide.FS.writeFile('/app/' + f, t);
  }
  for (const f of VERI_IKILI) {
    const buf = new Uint8Array(await (await fetch('motor/' + f)).arrayBuffer());
    pyodide.FS.writeFile('/app/' + f, buf);
  }

  // 4) motoru içe aktar ve köprü fonksiyonlarını tanımla
  await pyodide.runPythonAsync(`
import sys, json
sys.path.insert(0, '/app')
import sozluk as _szmod
import oneri as _oneri
import disa_aktar as _disa
_SZ = _szmod.Sozluk('/app/sozluk.xlsx')
_KARNE = json.load(open('/app/karne.json', encoding='utf-8'))

def _meta():
    return json.dumps(dict(
        uyari_esigi=float(_SZ.p('uyari_esigi', 0.15)),
        min_format=int(_SZ.p('min_format_cesidi', 3)),
        kirilim=str(_SZ.p('karne_kirilim', 'ana tür')),
        karne_hucre=len(_KARNE),
        sektorler=sorted({c['s2'] for c in _KARNE}),
        amaclar=sorted({t['amac'] for t in _SZ.turler.values() if t.get('amac')}),
    ), ensure_ascii=False)

def _marka(ad):
    s1, s2, s3, yok = _SZ.sektor(ad)
    return json.dumps(dict(s2=s2, bulundu=(not yok)), ensure_ascii=False)

def _gezgin(sektor):
    return json.dumps(_oneri.gezgin(dict(sektor_l2=sektor), _KARNE, _SZ), ensure_ascii=False)

def _filtreler(sektor, amac):
    b = dict(sektor_l2=sektor, amac=amac, toplam_butce=1, istenen_format_cesidi=None)
    return json.dumps(_oneri.filtre_secenekleri(b, _KARNE, _SZ), ensure_ascii=False)

def _oneri_uret(brief_json):
    return json.dumps(_oneri.oneri_uret(json.loads(brief_json), _KARNE, _SZ), ensure_ascii=False)

def _excel(kayit_json):
    return _disa.plan_excel_b64(json.loads(kayit_json))
`);

  const pyMeta = pyodide.globals.get('_meta');
  const pyMarka = pyodide.globals.get('_marka');
  const pyGezgin = pyodide.globals.get('_gezgin');
  const pyFiltre = pyodide.globals.get('_filtreler');
  const pyOneri = pyodide.globals.get('_oneri_uret');
  const pyExcel = pyodide.globals.get('_excel');

  window.MOTOR = {
    meta: JSON.parse(pyMeta()),
    marka: async (ad) => JSON.parse(pyMarka(ad)),
    gezgin: async (sektor) => JSON.parse(pyGezgin(sektor)),
    filtreler: async (sektor, amac) => JSON.parse(pyFiltre(sektor, amac)),
    oneri: async (brief) => JSON.parse(pyOneri(JSON.stringify(brief))),
    excel: async (kayit) => ({ b64: pyExcel(JSON.stringify(kayit)) }),
  };
})();
