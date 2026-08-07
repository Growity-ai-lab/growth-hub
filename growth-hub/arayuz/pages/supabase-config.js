/* Growth Hub — Supabase merkezi karar defteri yapılandırması.
 *
 * url + anonKey doldurulunca "Planı kaydet" düğmesi kararları Supabase Postgres'e yazar;
 * boş bırakılırsa arayüz JSONL indirmeye düşer (yerel yedek). Yapılandırma kurulumu ve
 * gerekli tablo/RLS/trigger SQL'i: dokuman/supabase-kurulum.md
 *
 * NOT: anonKey PUBLIC "anon" anahtardır (service_role DEĞİL). RLS yalnız-ekleme politikasıyla
 * korunur; istemcide (bu dosyada / Pages'te) durması Supabase'in tasarımı gereği güvenlidir.
 * Anahtarı repoya koymak istemezseniz GitHub Actions değişkeninden üretmeyi de seçebilirsiniz
 * (bkz. dokuman/supabase-kurulum.md).
 */
window.SUPABASE = {
  url: '',       // ör. https://xxxxxxxxxxxx.supabase.co
  anonKey: '',   // Supabase > Project Settings > API > Project API keys > anon public
};
