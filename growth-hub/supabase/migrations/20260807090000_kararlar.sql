-- Growth Hub — merkezi karar defteri (Supabase Postgres).
-- Supabase GitHub entegrasyonu bu dosyayı otomatik uygular. Elle de çalıştırılabilir
-- (SQL Editor). Ayrıntı: dokuman/supabase-kurulum.md

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

-- RLS: anon anahtar YALNIZCA ekleyebilir; okuyamaz/güncelleyemez/silemez (defter değişmez).
alter table public.kararlar enable row level security;

drop policy if exists karar_ekle on public.kararlar;
create policy karar_ekle on public.kararlar
  for insert to anon with check (true);

-- "Sapabilir ama sebebini yazmak zorundadır" — kuralı DB'de de uygula.
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
