import { createClient } from '@supabase/supabase-js'

// Usado SOMENTE para autenticação. Dados financeiros sempre via API privada.
export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL ?? 'http://127.0.0.1:54321',
  import.meta.env.VITE_SUPABASE_ANON_KEY ?? '',
  { auth: { persistSession: true, autoRefreshToken: true } },
)
