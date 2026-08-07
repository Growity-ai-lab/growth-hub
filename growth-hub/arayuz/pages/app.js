/* Growth Hub — paylaşılan arayüz mantığı (yerel sunucu + Pyodide Pages ortak).
 *
 * Bu dosya HİÇBİR öneri sayısını hesaplamaz (K3). MOTOR üzerinden gerçek motora sorar:
 *   MOTOR.meta                       -> {uyari_esigi, min_format, kirilim, karne_hucre, sektorler[], amaclar[]}
 *   MOTOR.filtreler(sektor, amac)    -> {yayinci: [reklam modelleri]}
 *   MOTOR.oneri(brief)               -> plan sözlüğü (oneri.py oneri_uret çıktısı)
 * MOTOR'u sağlayan katman (sunucu fetch'i ya da Pyodide) her iki barındırmada farklıdır.
 */
const $ = s => document.querySelector(s);
const tl = n => Number(n || 0).toLocaleString('tr-TR');
let META = null, PLAN = null, FILTRE = {};   // FILTRE: {yayinci: Set(seçili modeller) | 'HEPSI'}

async function basla() {
  const yuk = $('#yukleniyor'); if (yuk) yuk.style.display = 'none';
  $('#form-kart').style.display = 'block';
  try { META = await MOTOR.meta; } catch (e) { META = MOTOR.meta; }
  $('#sektor').innerHTML = META.sektorler.map(s => `<option>${s}</option>`).join('');
  $('#amac').innerHTML = META.amaclar.map(s => `<option>${s}</option>`).join('');
  $('#esik').textContent = Math.round(META.uyari_esigi * 100);
  $('#meta').textContent =
    `Karne: ${META.karne_hucre} hücre · kırılım: ${META.kirilim} · uyarı eşiği %${Math.round(META.uyari_esigi * 100)}`;
  $('#sektor').addEventListener('change', filtreleriYenile);
  $('#amac').addEventListener('change', filtreleriYenile);
  $('#oner').addEventListener('click', oner);
  $('#detay').addEventListener('change', () => document.body.classList.toggle('detayli', $('#detay').checked));
  const kb = $('#kaydet'); if (kb) kb.addEventListener('click', kaydet);
  $('#indir').addEventListener('click', indir);
  if (window.SUPABASE && window.SUPABASE.url) { const t = $('#defter-durum'); if (t) t.textContent = 'Kararlar merkezi deftere (Supabase) yazılır.'; }
  document.querySelectorAll('[data-preset]').forEach(b =>
    b.addEventListener('click', () => { $('#butce').value = b.dataset.preset; }));
  await filtreleriYenile();
}

/* --- platform filtresi: sektör/amaç değişince seçilebilir yayıncıları tazele --- */
async function filtreleriYenile() {
  const sektor = $('#sektor').value, amac = $('#amac').value;
  const secenek = await MOTOR.filtreler(sektor, amac);
  FILTRE = {};
  const kutu = $('#filtre-liste');
  const adlar = Object.keys(secenek);
  if (!adlar.length) { kutu.innerHTML = '<div class="mini">Bu seçim için yayıncı yok.</div>'; return; }
  kutu.innerHTML = adlar.map(y => {
    const modeller = secenek[y].map(m =>
      `<label class="mdl"><input type="checkbox" data-y="${y}" data-m="${m}" checked> ${m}</label>`).join('');
    return `<div class="yayinci-satir">
      <label class="yy"><input type="checkbox" class="y-onay" data-y="${y}"> <b>${y}</b></label>
      <div class="modeller" data-for="${y}" hidden>${modeller}</div></div>`;
  }).join('');
  kutu.querySelectorAll('.y-onay').forEach(cb => cb.addEventListener('change', () => {
    const y = cb.dataset.y;
    kutu.querySelector(`.modeller[data-for="${y}"]`).hidden = !cb.checked;
    guncelleFiltreDurum();
  }));
  kutu.querySelectorAll('.modeller input').forEach(cb => cb.addEventListener('change', guncelleFiltreDurum));
  guncelleFiltreDurum();
}

function guncelleFiltreDurum() {
  const secili = [...document.querySelectorAll('.y-onay:checked')].map(cb => cb.dataset.y);
  $('#filtre-ozet').textContent = secili.length
    ? `Filtre: yalnız ${secili.join(', ')} (grup tavanı ve deneme payı gevşer)`
    : 'Filtre yok — sistem tüm uygun yayıncılardan en iyi planı kurar.';
}

/* seçili filtreyi brief alanlarına çevir */
function filtreBrief() {
  const secili = [...document.querySelectorAll('.y-onay:checked')].map(cb => cb.dataset.y);
  if (!secili.length) return { yayinci_filtre: null, reklam_modeli_filtre: null };
  const rmf = {};
  secili.forEach(y => {
    const kutular = [...document.querySelectorAll(`.modeller[data-for="${y}"] input`)];
    const secilenler = kutular.filter(c => c.checked).map(c => c.dataset.m);
    if (secilenler.length && secilenler.length < kutular.length) rmf[y] = secilenler;  // alt küme ise sınırla
  });
  return { yayinci_filtre: secili, reklam_modeli_filtre: Object.keys(rmf).length ? rmf : null };
}

async function oner() {
  const btn = $('#oner'); btn.disabled = true; btn.textContent = 'Hesaplanıyor…';
  try {
    const f = filtreBrief();
    const brief = {
      sektor_l2: $('#sektor').value, amac: $('#amac').value,
      toplam_butce: Number($('#butce').value || 0), istenen_format_cesidi: null,
      yayinci_filtre: f.yayinci_filtre, reklam_modeli_filtre: f.reklam_modeli_filtre,
    };
    if (!brief.toplam_butce) { uyar('Lütfen bir bütçe girin.'); return; }
    const p = await MOTOR.oneri(brief);
    if (p.hata) { uyar(p.hata); return; }
    ciz(p);
  } catch (e) {
    uyar('Öneri üretilemedi: ' + (e && e.message ? e.message : e));
  } finally {
    btn.disabled = false; btn.textContent = 'Öneri getir';
  }
}

function uyar(msg) { $('#uyarilar').innerHTML = `<div class="uyari kotu">✕ ${msg}</div>`; }

function cubuk(puan, aralik) {
  const alt = Math.max(0, puan - aralik), ust = Math.min(200, puan + aralik), gen = (ust - alt) / 2;
  return `<div class="cubuk" title="ne kadar emin olduğumuz"><i style="left:${alt / 2}%;width:${gen}%"></i></div>`;
}

function ciz(p) {
  PLAN = p;
  $('#uyarilar').innerHTML = (p.uyarilar || []).map(u => `<div class="uyari">⚠ ${u}</div>`).join('');
  $('#sonuc-kart').style.display = 'block';
  const b = p.brief;
  const gruplar = new Set(p.satirlar.map(s => s.grup)).size;
  const denemeN = p.satirlar.filter(s => s.deneme).length;
  $('#baslik').textContent = `${b.sektor_l2} · ${b.amac} · ${tl(b.toplam_butce)} ₺`;
  $('#ozet').innerHTML =
    `Dağıtılan <b>${tl(p.toplam_dagitilan)} ₺</b> · ${p.satirlar.length} yayıncı · ${gruplar} grup` +
    (denemeN ? ` · ${denemeN} deneme` : '') +
    (p.filtre_aktif ? ' · <span class="etkin">platform filtresi açık</span>' : '');
  if (!p.satirlar.length) { $('#tablo-sar').innerHTML = '<div class="bos">Bu seçim için uygun yayıncı bulunamadı.</div>'; return; }

  // orijinal PLAN.satirlar indeksini koru (sapma/kayıt bu indekse göre çalışır)
  const idx = p.satirlar.map((s, i) => ({ s, i }));
  const cekirdek = idx.filter(x => !x.s.deneme);
  const deneme = idx.filter(x => x.s.deneme);
  let h = tablo(cekirdek);
  if (deneme.length) {
    h += `<div class="alt-baslik">Deneme payı — az tanıdığımız, şans verdiğimiz yayıncılar</div>`;
    h += tablo(deneme);
  }
  $('#tablo-sar').innerHTML = h;
  $('#durum').innerHTML = '';
  document.querySelectorAll('.butce-in').forEach(inp => inp.addEventListener('input', sapmaKontrol));
  sapmaKontrol();
}

function tablo(rows) {
  let h = `<table><thead><tr>
    <th>Yayıncı</th><th>Reklam modeli</th>
    <th class="sag">Fayda</th>
    <th class="detay">Puan</th><th class="sag detay">Önerilen birim</th>
    <th class="sag">Sistem bütçesi</th><th class="sag">Senin bütçen</th></tr></thead><tbody>`;
  rows.forEach(({ s, i }) => {
    h += `<tr>
      <td><b>${s.yayinci}</b><div class="mini">${s.grup}</div></td>
      <td>${s.reklam_modeli}<div class="mini guven-${(s.guven||'').replace(/\s/g,'')}">${s.guven}</div></td>
      <td class="sag"><b>${s.fayda}</b></td>
      <td class="detay">${s.puan} <span class="emin">± ${s.aralik}</span>${cubuk(s.puan, s.aralik)}</td>
      <td class="sag detay">${tl(s.oner)}<div class="mini">${s.oner_kaynak}, ${s.oner_n} gözlem</div></td>
      <td class="sag">${tl(s.sistem_butce)} ₺</td>
      <td class="sag">
        <input class="butce-in" type="number" data-i="${i}" value="${s.sistem_butce}">
        <input class="sebep-in" data-i="${i}" placeholder="sapma sebebi (zorunlu)">
      </td></tr>
      <tr class="detay"><td colspan="7" class="neden">↳ ${s.sistem_gerekcesi}</td></tr>`;
  });
  return h + '</tbody></table>';
}

function sapma(i) {
  const sis = PLAN.satirlar[i].sistem_butce;
  const sec = Number(document.querySelector(`.butce-in[data-i="${i}"]`).value || 0);
  return sis ? Math.abs(sec - sis) / sis : (sec ? 1 : 0);
}
function sapmaKontrol() {
  document.querySelectorAll('.butce-in').forEach(inp => {
    const i = +inp.dataset.i;
    document.querySelector(`.sebep-in[data-i="${i}"]`).classList.toggle('gerek', sapma(i) > META.uyari_esigi);
  });
}

/* "sapabilir ama sebebini yazmak zorundadır" — eşik üstü sapmada boş sebepli yayıncılar */
function sebepEksikleri() {
  const eksik = [];
  PLAN.satirlar.forEach((s, i) => {
    const seb = document.querySelector(`.sebep-in[data-i="${i}"]`).value.trim();
    if (sapma(i) > META.uyari_esigi && !seb) eksik.push(s.yayinci);
  });
  return eksik;
}

function kararKaydiKur() {
  const zaman = new Date().toISOString().slice(0, 19);
  const satirlar = PLAN.satirlar.map((s, i) => {
    const sec = Number(document.querySelector(`.butce-in[data-i="${i}"]`).value || 0);
    return {
      yayinci: s.yayinci, grup: s.grup, reklam_modeli: s.reklam_modeli, ana_tur: s.ana_tur, tip: s.tip,
      sistem_butce: s.sistem_butce, secilen_butce: sec, sistem_birim: s.oner, secilen_birim: s.oner,
      sapma_butce: Math.round((sec - s.sistem_butce) * 100) / 100, sapma_birim: 0, deneme: s.deneme,
      sebep: document.querySelector(`.sebep-in[data-i="${i}"]`).value.trim(),
      sebep_gerekli: sapma(i) > META.uyari_esigi,
    };
  });
  return {
    zaman, kullanici: 'arayuz', tur: 'secim',
    oneri_id: `${PLAN.brief.sektor_l2}-${PLAN.brief.amac}-${PLAN.brief.toplam_butce}`,
    brief: PLAN.brief, satirlar,
  };
}

function jsonlIndir(kayit) {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(kayit) + '\n'], { type: 'application/x-ndjson' }));
  a.download = `karar-${kayit.zaman.replace(/[:T]/g, '-')}.jsonl`;
  a.click(); URL.revokeObjectURL(a.href);
}

/* Supabase Postgres'e (merkezi karar defteri) yaz. Yapılandırılmamışsa {yok:true} döner.
   Anon public key + RLS (yalnız-ekleme) ile güvenli; sebep zorunluluğunu DB trigger'ı da uygular. */
async function supabaseYaz(kayit) {
  const cfg = window.SUPABASE || {};
  if (!cfg.url || !cfg.anonKey) return { yok: true };
  const r = await fetch(cfg.url.replace(/\/$/, '') + '/rest/v1/kararlar', {
    method: 'POST',
    headers: { apikey: cfg.anonKey, Authorization: 'Bearer ' + cfg.anonKey,
               'Content-Type': 'application/json', Prefer: 'return=minimal' },
    body: JSON.stringify(kayit),
  });
  if (!r.ok) throw new Error('Supabase ' + r.status + ': ' + (await r.text()).slice(0, 200));
  return { ok: true };
}

/* Planı kaydet: Supabase varsa oraya yaz, yoksa JSONL indir. Eşik üstü sapmada sebep zorunlu. */
async function kaydet() {
  const d = $('#durum');
  const eksik = sebepEksikleri();
  if (eksik.length) { d.className = 'durum hata'; d.textContent = '✕ Sapma sebebi yazılmamış yayıncılar var: ' + eksik.join(', '); return; }
  const kayit = kararKaydiKur();
  try {
    const res = await supabaseYaz(kayit);
    if (res.yok) { jsonlIndir(kayit); d.className = 'durum ok'; d.textContent = '✓ Supabase yapılandırılmadı — plan JSONL olarak indirildi.'; }
    else { d.className = 'durum ok'; d.textContent = '✓ Karar defterine (Supabase) yazıldı.'; }
  } catch (e) {
    jsonlIndir(kayit);
    d.className = 'durum hata'; d.textContent = '✕ Supabase’e yazılamadı (' + (e.message || e) + '). Yedek olarak JSONL indirildi.';
  }
}

/* Her zaman yerel yedek indir (sebep kuralını yine uygular). */
function indir() {
  const d = $('#durum');
  const eksik = sebepEksikleri();
  if (eksik.length) { d.className = 'durum hata'; d.textContent = '✕ Sapma sebebi yazılmamış yayıncılar var: ' + eksik.join(', '); return; }
  jsonlIndir(kararKaydiKur());
  d.className = 'durum ok'; d.textContent = '✓ JSONL indirildi (yerel yedek).';
}

/* MOTOR hazır olunca (sunucu: hemen, Pyodide: motor yüklenince) arayüzü başlat */
(window.MOTOR_READY || Promise.resolve()).then(basla).catch(e => {
  const y = document.querySelector('#yukleniyor');
  if (y) { y.className = 'uyari kotu'; y.textContent = 'Motor yüklenemedi: ' + (e && e.message ? e.message : e); }
});
