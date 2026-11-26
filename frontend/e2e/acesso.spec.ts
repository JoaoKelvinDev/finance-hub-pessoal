import { anonTest, expect, makeToken, test } from './fixtures'

anonTest('sem sessão, o app leva ao login e não mostra dados', async ({ page }) => {
  await page.goto('/lancamentos')
  await expect(page).toHaveURL(/\/entrar$/)
  await expect(page.getByRole('heading', { name: 'Finance Hub' })).toBeVisible()
  await expect(page.getByLabel('E-mail')).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Navegação principal' })).toHaveCount(0)
})

anonTest('a API recusa chamadas sem token ou com token de outra pessoa', async ({ request }) => {
  const api = 'http://127.0.0.1:8010/api/v1/accounts'
  expect((await request.get(api)).status()).toBe(401)
  // Token válido, mas assinado com outro segredo.
  const forged = makeToken().token.replace(/\.[^.]+$/, '.assinatura-invalida')
  expect((await request.get(api, { headers: { Authorization: `Bearer ${forged}` } })).status()).toBe(401)
})

test('com sessão, abre a visão geral e o login redireciona para dentro', async ({ page, checkA11y }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1, name: 'Visão geral' })).toBeVisible()
  await page.goto('/entrar')
  await expect(page).toHaveURL(/127\.0\.0\.1:\d+\/$/)
  await checkA11y(page)
})

test('sair encerra a sessão mesmo com o servidor de autenticação fora do ar', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Sair' }).click()
  await expect(page).toHaveURL(/\/entrar$/)
  // A sessão não volta ao recarregar.
  await page.reload()
  await expect(page).toHaveURL(/\/entrar$/)
  expect(await page.evaluate(() => localStorage.getItem('sb-127-auth-token'))).toBeNull()
})
