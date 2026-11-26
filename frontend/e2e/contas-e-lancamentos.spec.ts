import { brl, expect, test } from './fixtures'

test('criar conta, lançar receita e despesa e ver saldo e visão geral', async ({ page, checkA11y }) => {
  await page.goto('/contas')
  await expect(page.getByText('Nenhuma conta cadastrada')).toBeVisible()

  // Nova conta com saldo inicial de R$ 1.500,00.
  await page.getByRole('button', { name: 'Nova conta' }).click()
  const conta = page.getByRole('dialog', { name: 'Nova conta' })
  await conta.getByLabel('Nome').fill('Banco E2E')
  const saldo = conta.getByLabel('Saldo inicial', { exact: true })
  await saldo.fill('150000')
  await expect(saldo).toHaveValue('1.500,00')
  await checkA11y(page)
  await conta.getByRole('button', { name: 'Criar conta' }).click()
  await expect(page.getByText('Conta “Banco E2E” criada.')).toBeVisible()
  const card = page.getByRole('link', { name: /Banco E2E/ })
  await expect(card).toContainText(brl(1500))

  // Receita de R$ 3.200,00.
  await page.getByRole('button', { name: 'Novo lançamento' }).click()
  let tx = page.getByRole('dialog', { name: 'Novo lançamento' })
  await tx.getByRole('tab', { name: 'Receita' }).click()
  await tx.getByLabel('Valor').fill('320000')
  await tx.getByLabel('Descrição').fill('Salário E2E')
  await tx.getByRole('button', { name: 'Salvar' }).click()
  await expect(page.getByText(`Receita de ${brl(3200)} registrada.`)).toBeVisible()

  // Despesa de R$ 245,90 com categoria.
  await page.getByRole('button', { name: 'Novo lançamento' }).click()
  tx = page.getByRole('dialog', { name: 'Novo lançamento' })
  await expect(tx.getByRole('tab', { name: 'Despesa' })).toHaveAttribute('aria-selected', 'true')
  await tx.getByLabel('Valor').fill('24590')
  await tx.getByLabel('Descrição').fill('Mercado E2E')
  await tx.getByLabel('Categoria').selectOption({ label: 'Mercado' })
  await tx.getByRole('button', { name: 'Salvar' }).click()
  await expect(page.getByText(`Despesa de ${brl(245.9)} registrada.`)).toBeVisible()

  // Validação: despesa sem valor não é enviada.
  await page.getByRole('button', { name: 'Novo lançamento' }).click()
  tx = page.getByRole('dialog', { name: 'Novo lançamento' })
  await tx.getByLabel('Descrição').fill('Sem valor')
  await tx.getByRole('button', { name: 'Salvar' }).click()
  await expect(tx.getByRole('alert')).toContainText('Informe um valor maior que zero.')
  await tx.getByRole('button', { name: 'Cancelar' }).click()
  await expect(tx).toBeHidden()

  // 1.500 + 3.200 − 245,90 = 4.454,10
  await expect(card).toContainText(brl(4454.1))

  await page.goto('/lancamentos')
  await expect(page.getByText('Salário E2E')).toBeVisible()
  await expect(page.getByText('Mercado E2E')).toBeVisible()
  await expect(page.getByText('Sem valor')).toHaveCount(0)
  await checkA11y(page)

  await page.goto('/')
  await expect(page.getByRole('link', { name: /Saldo disponível/ })).toContainText(brl(4454.1))
  await expect(page.getByRole('link', { name: /Receitas/ }).first()).toContainText(brl(3200))
  await expect(page.getByRole('link', { name: /Despesas/ }).first()).toContainText(brl(245.9))
  await checkA11y(page)
})

test('transferência entre contas não muda o total, só move o saldo', async ({ page, api }) => {
  const { createAccount } = await import('./fixtures')
  await createAccount(api, 'Conta corrente', 100_000)
  await createAccount(api, 'Carteira', 0, 'CASH')

  await page.goto('/contas')
  await page.getByRole('button', { name: 'Novo lançamento' }).click()
  const tx = page.getByRole('dialog', { name: 'Novo lançamento' })
  await tx.getByRole('tab', { name: 'Transferência' }).click()
  await tx.getByLabel('Valor').fill('30000')
  await tx.getByLabel('De (origem)').selectOption({ label: `Conta corrente · ${brl(1000)}` })
  await tx.getByLabel('Para (destino)').selectOption({ label: 'Carteira' })
  await tx.getByRole('button', { name: 'Salvar' }).click()
  await expect(page.getByText(`Transferência de ${brl(300)} registrada.`)).toBeVisible()

  await expect(page.getByRole('link', { name: /Conta corrente/ })).toContainText(brl(700))
  await expect(page.getByRole('link', { name: /Carteira/ })).toContainText(brl(300))

  await page.goto('/')
  await expect(page.getByRole('link', { name: /Saldo disponível/ })).toContainText(brl(1000))
  // Transferência não é receita nem despesa.
  await expect(page.getByRole('link', { name: /Despesas/ }).first()).toContainText(brl(0))
})
