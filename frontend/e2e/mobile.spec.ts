import { brl, createAccount, expect, test } from './fixtures'

// Roda no projeto "celular" (Pixel 7), definido em playwright.config.ts.
test('no celular: menu inferior navega e o botão + lança uma despesa', async ({ page, api, checkA11y }) => {
  await createAccount(api, 'Carteira', 20_000, 'CASH')

  await page.goto('/')
  const nav = page.getByRole('navigation', { name: 'Navegação', exact: true })
  await expect(nav).toBeVisible()
  await expect(page.getByRole('navigation', { name: 'Navegação principal' })).toBeHidden()
  await checkA11y(page)

  await nav.getByRole('link', { name: 'Contas' }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Contas e carteiras' })).toBeVisible()
  await expect(page.getByRole('link', { name: /Carteira/ })).toContainText(brl(200))

  await nav.getByRole('button', { name: 'Novo lançamento' }).click()
  const tx = page.getByRole('dialog', { name: 'Novo lançamento' })
  await tx.getByLabel('Valor').fill('1250')
  await tx.getByLabel('Descrição').fill('Café E2E')
  await tx.getByRole('button', { name: 'Salvar' }).click()
  await expect(page.getByText(`Despesa de ${brl(12.5)} registrada.`)).toBeVisible()
  await expect(page.getByRole('link', { name: /Carteira/ })).toContainText(brl(187.5))

  await nav.getByRole('link', { name: 'Lançamentos' }).click()
  await expect(page.getByText('Café E2E')).toBeVisible()

  // Nada fica escondido atrás do menu inferior nem estoura a largura da tela.
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
  expect(overflow).toBeLessThanOrEqual(0)
})
