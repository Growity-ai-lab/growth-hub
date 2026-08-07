/* Growth Hub — seçim-önce arayüz (yerel sunucu + Pyodide Pages ortak).
 *
 * Ekip karneyi tarar (yayıncı × reklam modeli), Puan ya da gerçekleşen sonuçlara göre bakar,
 * beğendiğini kendi planına ekler. Hiçbir sayı burada hesaplanmaz (K3) — MOTOR üzerinden gelir:
 *   MOTOR.meta                    -> {uyari_esigi, kirilim, karne_hucre, sektorler[], amaclar[]}
 *   MOTOR.gezgin(sektor)          -> {sektor_geri, hucreler[]}   (tüm kanıtıyla karne hücreleri)
 *   MOTOR.oneri(brief)            -> plan (opsiyonel "sistem önerisi ile doldur")
 */
const $ = s => document.querySelector(s);
const tl = n => Number(n || 0).toLocaleString('tr-TR');
const HACIM_ETIKET = { CPM: 'gösterim', CPV: 'izlenme', CPC: 'tıklama' };
let META = null, HUCRELER = [], PLAN = [], MOD = 'puan';

const anah = c => `${c.yayinci}|${c.reklam_modeli}|${c.tip}`;
const yoksa = v => (v === null || v === undefined || v === '') ? '—' : v;

async function basla() {
  const y = $('#yukleniyor'); if (y) y.style.display = 'none';
  $('#form-kart').style.display = 'block';
  try { META = await MOTOR.meta; } catch (e) { META = MOTOR.meta; }
  $('#sektor').innerHTML = META.sektorler.map(s => `<option>${s}</option>`).join('');
  $('#amac').innerHTML = META.amaclar.map(s => `<option>${s}</option>`).join('');
  $('#meta').textContent = `Karne: ${META.karne_hucre} hücre · kırılım: ${META.kirilim} · uyarı eşiği %${Math.round(META.uyari_esigi * 100)}`;
  $('#sektor').addEventListener('change', gezginYukle);
  $('#mod-puan').addEventListener('click', () => setMod('puan'));
  $('#mod-sonuc').addEventListener('click', () => setMod('sonuc'));
  $('#oneri-doldur').addEventListener('click', oneriDoldur);
  $('#plan-temizle').addEventListener('click', () => { PLAN = []; planCiz(); gezginCiz(); });
  $('#kaydet').addEventListener('click', kaydet);
  $('#indir').addEventListener('click', indir);
  if (window.SUPABASE && window.SUPABASE.url) $('#defter-durum').textContent = 'Kararlar merkezi deftere (Supabase) yazılır.';
  await gezginYukle();
}

function setMod(m) {
  MOD = m;
  $('#mod-puan').classList.toggle('aktif', m === 'puan');
  $('#mod-sonuc').classList.toggle('aktif', m === 'sonuc');
  gezginCiz();
}

async function gezginYukle() {
  const g = await MOTOR.gezgin($('#sektor').value);
  HUCRELER = g.hucreler || [];
  $('#uyarilar').innerHTML = g.sektor_geri
    ? '<div class="uyum uyum-fark">Bu sektörde az veri var; karne tüm sektörlerden gösteriliyor.</div>' : '';
  $('#gezgin-kart').style.display = 'block';
  $('#plan-kart').style.display = 'block';
  filtreKur();
  gezginCiz();
  planCiz();
}

function filtreKur() {
  const yayincilar = [...new Set(HUCRELER.map(c => c.yayinci))].sort();
  const modeller = [...new Set(HUCRELER.map(c => c.reklam_modeli))].sort();
  const kutu = (dizi, cls) => dizi.map(v =>
    `<label><input type="checkbox" class="${cls}" value="${v}"> ${v}</label>`).join('');
  $('#f-yayinci').innerHTML = kutu(yayincilar, 'fy');
  $('#f-model').innerHTML = kutu(modeller, 'fm');
  document.querySelectorAll('.fy,.fm').forEach(cb => cb.addEventListener('change', gezginCiz));
}

function seciliFiltre(cls) { return new Set([...document.querySelectorAll('.' + cls + ':checked')].map(c => c.value)); }

function suzulmus() {
  const fy = seciliFiltre('fy'), fm = seciliFiltre('fm');
  return HUCRELER.filter(c => (!fy.size || fy.has(c.yayinci)) && (!fm.size || fm.has(c.reklam_modeli)));
}

function guvenRozet(c) {
  const k = (c.guven || '').replace(/\s/g, '');
  const cls = c.guven === 'kendi verisi' ? 'kendi' : 'tahmin';
  return `<span class="rozet ${cls}" title="ne kadar emin olduğumuz">${c.guven}</span>`;
}
function cubuk(puan, aralik) {
  const alt = Math.max(0, puan - aralik), ust = Math.min(200, puan + aralik), gen = (ust - alt) / 2;
  return `<div class="cubuk"><i style="left:${alt / 2}%;width:${gen}%"></i></div>`;
}

function gezginCiz() {
  const rows = suzulmus();
  const ekliSet = new Set(PLAN.map(p => anah(p.c)));
  const basliklar = MOD === 'puan'
    ? `<th>Yayıncı</th><th>Reklam modeli</th><th>Tip</th><th class="sag">Puan</th><th class="sag">Fayda</th><th class="sag">Önerilen birim</th><th></th>`
    : `<th>Yayıncı</th><th>Reklam modeli</th><th>Tip</th><th class="sag">Yayınlanma</th><th class="sag">Planlanan→Gerçekleşen birim</th><th class="sag">VCR</th><th class="sag">Kampanya</th><th></th>`;
  if (!rows.length) { $('#gezgin-sar').innerHTML = '<div class="bos">Filtreye uyan hücre yok.</div>'; return; }
  let h = `<table><thead><tr>${basliklar}</tr></thead><tbody>`;
  rows.forEach(c => {
    const ekli = ekliSet.has(anah(c));
    const dugme = `<button class="ekle ${ekli ? 'ekli' : ''}" data-k="${anah(c)}">${ekli ? '✓ eklendi' : '+ Ekle'}</button>`;
    if (MOD === 'puan') {
      h += `<tr>
        <td><b>${c.yayinci}</b><div class="mini">${c.grup}</div></td>
        <td>${c.reklam_modeli} ${guvenRozet(c)}</td>
        <td>${c.tip}</td>
        <td class="sag">${c.puan} <span class="emin">± ${c.aralik}</span>${cubuk(c.puan, c.aralik)}</td>
        <td class="sag"><b>${c.fayda}</b></td>
        <td class="sag">${tl(c.oner)}<div class="mini">${c.oner_n} gözlem</div></td>
        <td class="sag">${dugme}</td></tr>`;
    } else {
      const sap = c.birim_sapma === null || c.birim_sapma === undefined ? ''
        : ` <span class="${c.birim_sapma <= 0 ? 'iyi' : 'kotu'}">(${c.birim_sapma > 0 ? '+' : ''}${c.birim_sapma}%)</span>`;
      const birim = (c.plan_birim ? tl(c.plan_birim) : '—') + ' → ' + (c.ger_birim ? tl(c.ger_birim) : '—') + sap;
      h += `<tr>
        <td><b>${c.yayinci}</b><div class="mini">${c.grup}</div></td>
        <td>${c.reklam_modeli} ${guvenRozet(c)}</td>
        <td>${c.tip}</td>
        <td class="sag">${c.teslim === null || c.teslim === undefined ? '—' : '%' + c.teslim}</td>
        <td class="sag">${birim}</td>
        <td class="sag">${c.vcr === null || c.vcr === undefined ? '—' : '%' + c.vcr}</td>
        <td class="sag">${c.kampanya} kampanya<div class="mini">${c.n} satır</div></td>
        <td class="sag">${dugme}</td></tr>`;
    }
  });
  $('#gezgin-sar').innerHTML = h + '</tbody></table>';
  document.querySelectorAll('.ekle').forEach(b => b.addEventListener('click', () => ekleCikar(b.dataset.k)));
}

function ekleCikar(k) {
  const i = PLAN.findIndex(p => anah(p.c) === k);
  if (i >= 0) { PLAN.splice(i, 1); }
  else {
    const c = HUCRELER.find(x => anah(x) === k);
    if (c) PLAN.push({ c, butce: 0, sistem_butce: null, deneme: false });
  }
  gezginCiz(); planCiz();
}

/* --- plan --- */
function hacim(butce, birim, tip) { if (!birim || birim <= 0) return null; return tip === 'CPM' ? butce / birim * 1000 : butce / birim; }
function kisa(n) { n = Math.round(n); return n >= 1e6 ? (n / 1e6).toLocaleString('tr-TR', { maximumFractionDigits: 1 }) + ' Mn' : n.toLocaleString('tr-TR'); }
function sapmaOran(p) { const s = p.sistem_butce; return s ? Math.abs(p.butce - s) / s : 0; }

function planCiz() {
  if (!PLAN.length) {
    $('#plan-sar').innerHTML = '<div class="bos">Karneden <b>+ Ekle</b> ile satır ekle ya da “Sistem önerisi ile doldur”.</div>';
    $('#uyum').style.display = 'none'; return;
  }
  let h = `<table><thead><tr><th>Yayıncı</th><th>Reklam modeli</th><th>Tip</th>
    <th class="sag">Önerilen birim</th><th class="sag">Bütçen</th><th></th></tr></thead><tbody>`;
  PLAN.forEach((p, i) => {
    const c = p.c;
    h += `<tr>
      <td><b>${c.yayinci}</b><div class="mini">${c.grup}${p.sistem_butce ? ' · sistem önerisi' : ''}</div></td>
      <td>${c.reklam_modeli}</td><td>${c.tip}</td>
      <td class="sag">${tl(c.oner)}</td>
      <td class="sag">
        <input class="butce-in" type="number" min="0" step="10000" data-i="${i}" value="${p.butce}">
        <div class="etki" data-i="${i}"></div>
        <input class="sebep-in" data-i="${i}" placeholder="sapma sebebi (zorunlu)">
      </td>
      <td class="sag"><button class="cikar" data-i="${i}">çıkar</button></td></tr>`;
  });
  $('#plan-sar').innerHTML = h + '</tbody></table>';
  document.querySelectorAll('.butce-in').forEach(inp => inp.addEventListener('input', e => { PLAN[+e.target.dataset.i].butce = Number(e.target.value || 0); etkiGuncelle(); }));
  document.querySelectorAll('.cikar').forEach(b => b.addEventListener('click', () => { PLAN.splice(+b.dataset.i, 1); gezginCiz(); planCiz(); }));
  etkiGuncelle();
}

function etkiGuncelle() {
  let toplam = 0;
  PLAN.forEach((p, i) => {
    toplam += p.butce;
    const et = document.querySelector(`.etki[data-i="${i}"]`);
    const seb = document.querySelector(`.sebep-in[data-i="${i}"]`);
    if (!et) return;
    const v = hacim(p.butce, p.c.oner, p.c.tip);
    const hac = v != null ? `≈ ${kisa(v)} ${HACIM_ETIKET[p.c.tip] || 'birim'}` : '';
    if (p.sistem_butce) {
      const dTL = p.butce - p.sistem_butce, dPct = p.sistem_butce ? dTL / p.sistem_butce * 100 : 0;
      const uyari = Math.abs(dPct) > META.uyari_esigi * 100;
      seb.classList.toggle('gerek', uyari);
      et.className = 'etki' + (uyari ? ' etki-uyari' : '');
      et.textContent = (dTL === 0 ? 'sistemle aynı' : `${dTL > 0 ? '+' : '−'}${Math.abs(dPct).toFixed(0)}% · ${dTL > 0 ? '+' : '−'}${tl(Math.abs(dTL))} ₺`) + (hac ? ' · ' + hac : '');
    } else {
      seb.classList.remove('gerek');
      et.className = 'etki';
      et.textContent = hac;
    }
  });
  const hedef = Number($('#butce').value || 0), fark = toplam - hedef, u = $('#uyum');
  u.style.display = 'block';
  if (!hedef) { u.className = 'uyum uyum-tam'; u.textContent = `Plan toplamı ${tl(toplam)} ₺`; }
  else if (Math.abs(fark) < 1) { u.className = 'uyum uyum-tam'; u.textContent = `Plan toplamı ${tl(toplam)} ₺ — hedef bütçeyle tam uyumlu.`; }
  else { u.className = 'uyum uyum-fark'; u.textContent = `Plan toplamı ${tl(toplam)} ₺ / ${tl(hedef)} ₺ — ${fark > 0 ? tl(fark) + ' ₺ FAZLA' : tl(-fark) + ' ₺ EKSİK'}.`; }
}

async function oneriDoldur() {
  const btn = $('#oneri-doldur'); btn.disabled = true; btn.textContent = 'Hesaplanıyor…';
  try {
    const plan = await MOTOR.oneri({
      sektor_l2: $('#sektor').value, amac: $('#amac').value,
      toplam_butce: Number($('#butce').value || 0), istenen_format_cesidi: null,
      yayinci_filtre: null, reklam_modeli_filtre: null,
    });
    if (plan.hata) { $('#durum').className = 'durum hata'; $('#durum').textContent = '✕ ' + plan.hata; return; }
    PLAN = plan.satirlar.map(s => ({
      c: { yayinci: s.yayinci, grup: s.grup, reklam_modeli: s.reklam_modeli, tip: s.tip, tur: s.ana_tur, oner: s.oner, guven: s.guven, puan: s.puan, aralik: s.aralik, fayda: s.fayda, oner_n: s.oner_n, teslim: s.teslim ?? null },
      butce: s.sistem_butce, sistem_butce: s.sistem_butce, deneme: s.deneme,
    }));
    $('#durum').innerHTML = '';
    (plan.uyarilar || []).forEach(() => {});
    $('#uyarilar').innerHTML = (plan.uyarilar || []).map(x => `<div class="uyum uyum-fark">⚠ ${x}</div>`).join('');
    gezginCiz(); planCiz();
  } catch (e) {
    $('#durum').className = 'durum hata'; $('#durum').textContent = '✕ Öneri üretilemedi: ' + (e.message || e);
  } finally { btn.disabled = false; btn.textContent = 'Sistem önerisi ile doldur'; }
}

/* --- kayıt (Supabase / JSONL), sebep zorunluluğu --- */
function sebepEksikleri() {
  const eksik = [];
  PLAN.forEach((p, i) => {
    if (!p.sistem_butce) return;
    const seb = document.querySelector(`.sebep-in[data-i="${i}"]`).value.trim();
    if (sapmaOran(p) > META.uyari_esigi && !seb) eksik.push(p.c.yayinci);
  });
  return eksik;
}
function kararKaydiKur() {
  const zaman = new Date().toISOString().slice(0, 19);
  const satirlar = PLAN.map((p, i) => {
    const c = p.c, sebep = (document.querySelector(`.sebep-in[data-i="${i}"]`) || {}).value || '';
    return {
      yayinci: c.yayinci, grup: c.grup, reklam_modeli: c.reklam_modeli, ana_tur: c.tur, tip: c.tip,
      sistem_butce: p.sistem_butce, secilen_butce: p.butce, sistem_birim: c.oner, secilen_birim: c.oner,
      sapma_butce: p.sistem_butce ? Math.round((p.butce - p.sistem_butce) * 100) / 100 : null, sapma_birim: 0,
      deneme: !!p.deneme, kaynak: p.sistem_butce ? 'öneri' : 'ekip',
      sebep: sebep.trim(), sebep_gerekli: !!p.sistem_butce && sapmaOran(p) > META.uyari_esigi,
    };
  });
  return {
    zaman, kullanici: 'arayuz', tur: 'secim',
    oneri_id: `${$('#sektor').value}-${$('#amac').value}-${$('#butce').value}`,
    brief: { sektor_l2: $('#sektor').value, amac: $('#amac').value, toplam_butce: Number($('#butce').value || 0) },
    satirlar,
  };
}
function jsonlIndir(kayit) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(kayit) + '\n'], { type: 'application/x-ndjson' }));
  a.download = `plan-${kayit.zaman.replace(/[:T]/g, '-')}.jsonl`;
  a.click(); URL.revokeObjectURL(a.href);
}
async function supabaseYaz(kayit) {
  const cfg = window.SUPABASE || {};
  if (!cfg.url || !cfg.anonKey) return { yok: true };
  const r = await fetch(cfg.url.replace(/\/$/, '') + '/rest/v1/kararlar', {
    method: 'POST',
    headers: { apikey: cfg.anonKey, Authorization: 'Bearer ' + cfg.anonKey, 'Content-Type': 'application/json', Prefer: 'return=minimal' },
    body: JSON.stringify(kayit),
  });
  if (!r.ok) throw new Error('Supabase ' + r.status + ': ' + (await r.text()).slice(0, 200));
  return { ok: true };
}
async function kaydet() {
  const d = $('#durum');
  if (!PLAN.length) { d.className = 'durum hata'; d.textContent = '✕ Plan boş.'; return; }
  const eksik = sebepEksikleri();
  if (eksik.length) { d.className = 'durum hata'; d.textContent = '✕ Sapma sebebi yazılmamış yayıncılar var: ' + eksik.join(', '); return; }
  const kayit = kararKaydiKur();
  try {
    const res = await supabaseYaz(kayit);
    if (res.yok) { jsonlIndir(kayit); d.className = 'durum ok'; d.textContent = '✓ Supabase yapılandırılmadı — plan JSONL olarak indirildi.'; }
    else { d.className = 'durum ok'; d.textContent = '✓ Karar defterine (Supabase) yazıldı.'; }
  } catch (e) { jsonlIndir(kayit); d.className = 'durum hata'; d.textContent = '✕ Supabase’e yazılamadı (' + (e.message || e) + '). Yedek olarak JSONL indirildi.'; }
}
function indir() {
  const d = $('#durum');
  if (!PLAN.length) { d.className = 'durum hata'; d.textContent = '✕ Plan boş.'; return; }
  const eksik = sebepEksikleri();
  if (eksik.length) { d.className = 'durum hata'; d.textContent = '✕ Sapma sebebi yazılmamış yayıncılar var: ' + eksik.join(', '); return; }
  jsonlIndir(kararKaydiKur()); d.className = 'durum ok'; d.textContent = '✓ JSONL indirildi (yerel yedek).';
}

(window.MOTOR_READY || Promise.resolve()).then(basla).catch(e => {
  const y = $('#yukleniyor'); if (y) { y.className = 'durum hata'; y.textContent = 'Motor yüklenemedi: ' + (e && e.message ? e.message : e); }
});
