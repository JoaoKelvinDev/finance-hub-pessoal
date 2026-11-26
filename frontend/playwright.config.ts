import { defineConfig, devices } from '@playwright/test'

// Testes E2E: API e frontend próprios, com banco isolado (finance_hub_e2e). Os dados do usuário nunca são tocados.
const API_PORT = 8010
const WEB_PORT = 5180
const CI = !!process.env.CI

export default defineConfig({
  testDir: './e2e',
  // Um único banco compartilhado: os testes rodam em sequência e cada um começa do zero.
  workers: 1,
  fullyParallel: false,
  forbidOnly: CI,
  retries: CI ? 1 : 0,
  timeout: 45_000,
  expect: { timeout: 8_000 },
  reporter: CI ? [['github'], ['html', { open: 'never' }]] : [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    locale: 'pt-BR',
    timezoneId: 'America/Fortaleza',
    // O app respeita "reduzir movimento": sem animações, o axe não mede contraste no meio de um fade.
    contextOptions: { reducedMotion: 'reduce' },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    // Localmente usa o Edge instalado (sem baixar navegador); no CI, o Chromium do Playwright.
    ...(CI ? {} : { channel: 'msedge' }),
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } }, testIgnore: /mobile/ },
    { name: 'celular', use: { ...devices['Pixel 7'] }, testMatch: /mobile/ },
  ],
  webServer: [
    {
      command: `uv run python scripts/e2e.py serve ${API_PORT}`,
      cwd: '../backend',
      url: `http://127.0.0.1:${API_PORT}/health`,
      timeout: 120_000,
      reuseExistingServer: false,
      stdout: 'pipe',
    },
    {
      command: `npx vite --port ${WEB_PORT} --strictPort --host 127.0.0.1`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        API_PROXY_TARGET: `http://127.0.0.1:${API_PORT}`,
        VITE_SUPABASE_URL: 'http://127.0.0.1:54321',
        VITE_SUPABASE_ANON_KEY: 'e2e-anon-key',
      },
    },
  ],
})
