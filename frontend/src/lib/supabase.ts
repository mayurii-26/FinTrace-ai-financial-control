import { createClient } from '@supabase/supabase-js';

const supabaseUrl  = import.meta.env.VITE_SUPABASE_URL  as string;
const supabaseAnon = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

if (!supabaseUrl || !supabaseAnon) {
  console.warn(
    '[FinTrace] Supabase env vars missing. Set VITE_SUPABASE_URL and ' +
    'VITE_SUPABASE_ANON_KEY in frontend/.env',
  );
}

export const supabase = createClient(supabaseUrl ?? '', supabaseAnon ?? '');
