import { execFileSync } from 'node:child_process'
import { createHmac } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import AxeBuilder from '@axe-core/playwright'
import { test as base, expect, type APIRequestContext, type Page } from '@playwright/test'

// Mesmos valores de backend/scripts/e2e.py.
const OWNER = '00000000-0000-4000-8000-0000000000e2'
const SECRET = 'e2e-secret-with-at-least-32-characters!!'
const API = 'http://127.0.0.1:8010/api/v1'
const BACKEND = fileURLToPath(new URL('../../backend', import.meta.url))
// Chave em que o supabase-js guarda a sessão para http://127.0.0.1:54321.
const STORAGE_KEY = 'sb-127-auth-token'

const b64 = (v: object | Buffer) => Buffer.from(v instanceof Buffer ? v : JSON.stringify(v)).toString('base64url')

/** JWT HS256 igual ao do Supabase Auth, assinado com o segredo de teste. */
export function makeToken(ttl = 3600) {
  const now = Math.floor(Date.now() / 1000)
  const head = b64({ alg: 'HS256', typ: 'JWT' })
  const body = b64({ sub: OWNER, aud: 'authenticated', role: 'authenticated', iat: now, exp: now + ttl })
  const sig = createHmac('sha256', SECRET).update(`${head}.${body}`).digest('base64url')
  return { token: `${head}.${body}.${sig}`, exp: now + ttl }
}

function session() {
  const { token, exp } = makeToken()
  return JSON.stringify({
    access_token: token,
    refresh_token: 'e2e',
    token_type: 'bearer',
    expires_in: 3600,
    expires_at: exp,
    user: { id: OWNER, aud: 'authenticated', role: 'authenticated', email: 'dono@e2e.local' },
  })
}

export function resetDatabase() {
  execFileSync('uv', ['run', 'python', 'scripts/e2e.py', 'reset'], { cwd: BACKEND, stdio: 'pipe' })
}

type Fixtures = {
  /** Página já autenticada como o proprietário (banco zerado antes de cada teste). */
  page: Page
  /** Cliente da API autenticado, para preparar dados sem passar pela interface. */
  api: APIRequestContext
  /** Falha o teste se houver violações de acessibilidade graves ou críticas. */
  checkA11y: (page: Page) => Promise<void>
}

/** Teste sem sessão (visitante anônimo). */
export const anonTest = base

export const test = base.extend<Fixtures>({
  page: async ({ page }, use) => {
    resetDatabase()
    await page.addInitScript(
      ([key, value]) => {
        localStorage.setItem(key, value)
        localStorage.setItem('fh-theme', 'dark')
      },
      [STORAGE_KEY, session()],
    )
    await use(page)
  },
  api: async ({ playwright }, use) => {
    const ctx = await playwright.request.newContext({
      baseURL: `${API}/`,
      extraHTTPHeaders: { Authorization: `Bearer ${makeToken().token}` },
    })
    await use(ctx)
    await ctx.dispose()
  },
  // O Playwright exige o padrão de objeto (mesmo vazio) no 1º parâmetro da fixture.
  // oxlint-disable-next-line no-empty-pattern
  checkA11y: async ({}, use) => {
    await use(async (page) => {
      // Espera transições terminarem (CSS/WAAPI) para não medir uma cor no meio do caminho.
      await page.waitForFunction(() => document.getAnimations().every((a) => a.playState !== 'running'), null, { timeout: 5_000 }).catch(() => {})
      const result = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21aa'])
        // Avisos temporários (toasts) entram e saem com fade; não fazem parte da página.
        .exclude('[data-sonner-toaster]')
        .analyze()
      const serious = result.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
      expect(
        serious.map((v) => `${v.id}: ${v.help} → ${v.nodes.map((n) => n.target.join(' ')).slice(0, 3).join(' | ')}`),
      ).toEqual([])
    })
  },
})

export { expect }

/** Data de hoje no fuso do app (America/Fortaleza), em ISO. */
export function todayISO() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Fortaleza' }).format(new Date())
}

/** Valor em reais como aparece na interface (ex.: 1234.5 → "R$ 1.234,50"). */
export function brl(value: number) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value).replace(/ /g, ' ')
}

/** Saldo atual (centavos) de uma conta, direto da API. */
export async function balanceOf(api: APIRequestContext, accountId: string): Promise<number> {
  const accounts: { id: string; balance_cents: number }[] = await (await api.get('accounts')).json()
  return accounts.find((a) => a.id === accountId)!.balance_cents
}

/** Cria conta pela API e devolve o JSON. */
export async function createAccount(api: APIRequestContext, name: string, openingCents: number, type = 'CHECKING') {
  const r = await api.post('accounts', {
    data: { name, type, opening_balance_cents: openingCents, opening_date: '2026-01-01' },
  })
  expect(r.status(), await r.text()).toBe(201)
  return r.json()
}
