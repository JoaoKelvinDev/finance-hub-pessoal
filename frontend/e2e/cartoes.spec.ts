import { balanceOf, brl, createAccount, expect, test } from './fixtures'

function br(iso: string) {
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}

test('compra parcelada vai para as faturas e o pagamento gera uma única saída', async ({ page, api, checkA11y }) => {
  const acc = await createAccount(api, 'Banco E2E', 200_000)

  // Cadastro do cartão pela interface.
  await page.goto('/cartoes')
  await page.getByRole('button', { name: 'Novo cartão' }).click()
  const novo = page.getByRole('dialog', { name: 'Novo cartão' })
  await novo.getByLabel('Nome do cartão *').fill('Roxinho E2E')
  await novo.getByLabel('Limite *').fill('500000')
  await novo.getByLabel('Dia do fechamento *').fill('10')
  await novo.getByLabel('Dia do vencimento *').fill('5')
  await novo.getByLabel('Conta padrão para pagamento').selectOption(acc.id)
  await novo.getByRole('button', { name: 'Cadastrar cartão' }).click()
  await expect(novo).toBeHidden()
  await expect(page.getByText('Roxinho E2E')).toBeVisible()

  await page.getByRole('button', { name: 'Ver detalhes' }).click()
  await expect(page.getByRole('heading', { name: 'Roxinho E2E' })).toBeVisible()

  // Compra de R$ 900,01 em 3x: 300,01 + 300,00 + 300,00 (centavo de sobra na 1ª parcela).
  await page.getByRole('button', { name: 'Nova compra' }).first().click()
  const compra = page.getByRole('dialog', { name: 'Nova compra no cartão' })
  await compra.getByLabel('Descrição *').fill('Notebook E2E')
  await compra.getByLabel('Valor total *').fill('90001')
  await compra.getByLabel('Parcelas *').selectOption('3')
  await compra.getByRole('button', { name: 'Registrar compra' }).click()
  await expect(page.getByText(`Compra de ${brl(900.01)} em 3x registrada.`)).toBeVisible()
  await expect(compra).toBeHidden()

  // A tela se atualiza sozinha após a compra (antes só atualizava ao recarregar).
  await expect(page.getByRole('tab', { name: 'Compras (1)' })).toBeVisible()
  // Uma fatura por parcela (antes as 3 parcelas caíam todas na 1ª fatura).
  await expect(page.getByRole('tab', { name: 'Faturas (3)' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Próximas parcelas (3)' })).toBeVisible()

  // A data exibida é a mesma da API (sem "um dia antes" por causa do fuso).
  const card = (await (await api.get('cards')).json()).find((c: { name: string }) => c.name === 'Roxinho E2E')
  const statements = await (await api.get(`cards/${card.id}/statements`)).json()
  const first = [...statements].sort((a: { due_date: string }, b: { due_date: string }) => a.due_date.localeCompare(b.due_date))[0]
  expect(first.total_cents).toBe(30_001)
  // A fatura nunca vence antes de fechar.
  for (const s of statements) expect(s.due_date > s.cycle_end_exclusive).toBe(true)
  await expect(page.getByText(`Vence em ${br(first.due_date)}`)).toBeVisible()
  await checkA11y(page)

  // Antes de pagar, a compra não mexe no saldo da conta.
  expect(await balanceOf(api, acc.id)).toBe(200_000)

  // Paga a primeira fatura inteira.
  const stmtCard = page.locator('div', { hasText: `Vence em ${br(first.due_date)}` }).filter({ has: page.getByRole('button', { name: 'Pagar fatura' }) }).last()
  await stmtCard.getByRole('button', { name: 'Pagar fatura' }).click()
  const pagar = page.getByRole('dialog', { name: 'Pagar fatura' })
  await expect(pagar.getByText(`Vencimento: ${br(first.due_date)}`)).toBeVisible()
  await pagar.getByLabel('Conta para débito *').selectOption(acc.id)
  await pagar.getByLabel('Valor do pagamento *').fill('30001')
  await pagar.getByRole('button', { name: 'Confirmar pagamento' }).click()
  // Antes desta correção, o pagamento pela interface sempre falhava sem mensagem (faltava a chave de idempotência).
  await expect(page.getByText(`Pagamento de ${brl(300.01)} registrado.`)).toBeVisible()
  await expect(pagar).toBeHidden()
  await expect(page.getByRole('tab', { name: 'Faturas (3)' })).toBeVisible()
  expect(await balanceOf(api, acc.id)).toBe(200_000 - 30_001)

  // Uma única saída de R$ 300,01 na conta; a compra em si não vira lançamento bancário.
  await page.goto('/lancamentos')
  await expect(page.getByText('Notebook E2E')).toHaveCount(0)
  const txs = (await (await api.get('transactions')).json()).items ?? []
  const saidas = txs.filter((t: { kind: string }) => t.kind === 'EXPENSE')
  expect(saidas).toHaveLength(1)
  expect(saidas[0].amount_cents).toBe(-30_001)

  await page.goto('/contas')
  await expect(page.getByRole('link', { name: /Banco E2E/ })).toContainText(brl(1699.99))
})
