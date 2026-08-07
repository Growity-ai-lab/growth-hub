# Supabase — merkezi karar defteri kurulumu

Arayüzdeki "Planı kaydet", öneriden sapmaları ve sebeplerini **merkezi** bir deftere yazar
(bugünkü "JSONL indir" yerine). Defter Supabase Postgres'te durur. Motor nerede koşarsa koşsun
(Pyodide ya da Python host) bu defter aynıdır — karar katmanının kalıcı hafızası (CLAUDE.md §7.3).

Yapılandırılmazsa arayüz otomatik olarak JSONL indirmeye düşer; yani Supabase **opsiyoneldir**.

## 1. Tablo + güvenlik (Supabase SQL Editor'de çalıştır)

```sql
-- Karar defteri: her satır bir "secim" kaydı (başlık + satırlar jsonb).
create table if not exists public.kararlar (
  id         uuid primary key default gen_random_uuid(),
  zaman      timestamptz,
  kullanici  text,
  tur        text,
  oneri_id   text,
  brief      jsonb,
  satirlar   jsonb,
  created_at timestamptz not null default now()
);

-- RLS: anon anahtar YALNIZCA ekleyebilir; okuyamaz/güncelleyemez/silemez.
alter table public.kararlar enable row level security;

create policy karar_ekle on public.kararlar
  for insert to anon with check (true);

-- "Sapabilir ama sebebini yazmak zorundadır" — kuralı DB'de de uygula (istemci de uygular).
create or replace function public.karar_sebep_kontrol() returns trigger
language plpgsql as $$
declare s jsonb;
begin
  for s in select * from jsonb_array_elements(coalesce(new.satirlar, '[]'::jsonb)) loop
    if coalesce((s->>'sebep_gerekli')::boolean, false)
       and coalesce(btrim(s->>'sebep'), '') = '' then
      raise exception 'Sapma sebebi yazılmamış: %', coalesce(s->>'yayinci', '?');
    end if;
  end loop;
  return new;
end $$;

drop trigger if exists karar_sebep on public.kararlar;
create trigger karar_sebep before insert on public.kararlar
  for each row execute function public.karar_sebep_kontrol();
```

> **Neden yalnız-ekleme (append-only):** defter geçmişi asla değişmemeli. Rapor/okuma
> (ileride "Öneriden farklar") anon anahtarla değil, Supabase Auth ya da service anahtarıyla
> yapılır — anon anahtar dünyaya açık olduğu için okuma yetkisi verilmez.

## 2. Anahtarları arayüze ver

`arayuz/pages/supabase-config.js` dosyasını doldur:

```js
window.SUPABASE = {
  url: 'https://xxxxxxxxxxxx.supabase.co',   // Project Settings > API > Project URL
  anonKey: 'eyJhbGciOi...',                  // Project Settings > API > anon public
};
```

`anonKey` **public "anon" anahtardır** (service_role DEĞİL). RLS ile korunduğu için istemcide
durması Supabase'in tasarımı gereği güvenlidir. `service_role` anahtarını ASLA buraya/istemciye koyma.

### Anahtarı repoya koymak istemezsen (opsiyonel)
GitHub Actions'ta iki **repository variable** tanımla: `SUPABASE_URL`, `SUPABASE_ANON_KEY`.
Sonra `.github/workflows/pages.yml`'e build adımından önce şunu ekle (deploy sırasında dosyayı üretir):

```yaml
      - name: Supabase yapılandırmasını yaz
        run: |
          cat > growth-hub/arayuz/pages/supabase-config.js <<EOF
          window.SUPABASE = { url: '${{ vars.SUPABASE_URL }}', anonKey: '${{ vars.SUPABASE_ANON_KEY }}' };
          EOF
```

## 3. Doğrulama
- Arayüzde bir öneri getir, bir satırın bütçesini eşik üstü değiştir, sebep **yazma** → "Planı kaydet"
  DB trigger'ı reddeder (istemci zaten uyarır).
- Sebebi yaz → kayıt Supabase `kararlar` tablosuna düşer (Table Editor'de gör).

## Kayıt şeması (JSONL ile aynı)
`zaman, kullanici, tur('secim'), oneri_id, brief{...}, satirlar[]`; her satır:
`yayinci, grup, reklam_modeli, ana_tur, tip, sistem_butce, secilen_butce, sistem_birim,
secilen_birim, sapma_butce, sapma_birim, deneme, sebep, sebep_gerekli`.
