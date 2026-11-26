import { createClient } from '@supabase/supabase-js'

// Usado SOMENTE para autenticação. Dados financeiros sempre via API privada.
export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL ?? 'http://127.0.0.1:54321',
  import.meta.env.VITE_SUPABASE_ANON_KEY ?? '',
  { auth: { persistSession: true, autoRefreshToken: true } },
)

export const SIGNED_OUT_EVENT = 'fh:signed-out'

/**
 * Encerra a sessão SEMPRE. O supabase-js só apaga a sessão local se o servidor de autenticação
 * responder; com ele fora do ar (ou sem rede), "Sair" não fazia nada e a sessão continuava salva.
 */
export async function signOutEverywhere() {
  // Revoga no servidor quando possível, mas sem prender a saída: com o servidor fora, o
  // supabase-js fica tentando e não responde.
  const revoked = await Promise.race([
    supabase.auth.signOut().then(({ error }) => !error, () => false),
    new Promise<boolean>((resolve) => setTimeout(() => resolve(false), 2500)),
  ])
  if (!revoked) {
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith('sb-') && key.endsWith('-auth-token')) localStorage.removeItem(key)
    }
  }
  window.dispatchEvent(new Event(SIGNED_OUT_EVENT))
}
