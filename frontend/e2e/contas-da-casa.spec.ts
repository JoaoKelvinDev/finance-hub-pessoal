import { balanceOf, brl, createAccount, expect, test, todayISO } from './fixtures'

test('conta da casa recorrente: gera parcela, paga e aparece no calendário', async ({ page, api, checkA11y }) => {
  const acc = await createAccount(api, 'Banco E2E', 100_000)
  const today = todayISO()
  const day = Number(today.slice(8, 10))

  await page.goto('/contas-da-casa')
  await page.getByRole('button', { name: 'Nova conta' }).first().click()
  const nova = page.getByRole('dialog', { name: 'Nova conta da casa' })
  await nova.getByLabel('Nome da conta *').fill('Internet E2E')
  await nova.getByLabel('Conta bancária *').selectOption(acc.id)
  await nova.getByLabel('Valor padrão *').fill('12990')
  await checkA11y(page)
  await nova.getByRole('button', { name: 'Cadastrar conta' }).click()
  await expect(nova).toBeHidden()
  await expect(page.getByRole('heading', { name: 'Internet E2E' })).toBeVisible()

  // Abre a conta pelo botão "Ver detalhes" (antes esse botão não fazia nada).
  await page.getByRole('button', { name: 'Expandir', exact: true }).first().click()
  await page.getByRole('button', { name: 'Ver detalhes' }).click()
  await expect(page.getByRole('tab', { name: 'Recorrências' })).toHaveAttribute('aria-selected', 'true')

  // Recorrência mensal vencendo hoje, a partir de hoje.
  await page.getByRole('button', { name: 'Nova recorrência' }).click()
  const rec = page.getByRole('dialog', { name: 'Nova recorrência' })
  await expect(rec.getByLabel('Data de início *')).toHaveValue(today) // fuso do app, não UTC
  await rec.getByLabel('Dia do vencimento *').fill(String(day))
  await rec.getByRole('button', { name: 'Criar recorrência' }).click()
  await expect(rec).toBeHidden()

  // Gera as parcelas até hoje e abre a lista pela recorrência.
  await page.getByRole('button', { name: 'Expandir', exact: true }).first().click()
  await page.getByRole('button', { name: 'Postar parcelas agora' }).click()
  await page.getByRole('button', { name: 'Ver parcelas' }).click()
  await expect(page.getByRole('tab', { name: 'Parcelas' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByText(brl(129.9)).first()).toBeVisible()

  // Paga a parcela de hoje.
  await page.getByText(brl(129.9)).first().click()
  const pagar = page.getByRole('dialog', { name: 'Pagar parcela' })
  await pagar.getByLabel('Conta de pagamento *').selectOption(acc.id)
  await pagar.getByRole('button', { name: 'Confirmar pagamento' }).click()
  await expect(page.getByText('Pagamento registrado.')).toBeVisible()
  await expect.poll(() => balanceOf(api, acc.id)).toBe(100_000 - 12_990)

  // O calendário mostra a próxima ocorrência (prevista) da conta.
  await page.goto('/calendario')
  await page.getByRole('tab', { name: 'Agenda' }).click()
  await expect(page.getByText('Internet E2E').first()).toBeVisible()
  await checkA11y(page)
})
