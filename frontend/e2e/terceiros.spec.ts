import { balanceOf, brl, createAccount, expect, test } from './fixtures'

test('emprestar e receber em parte: saldo em aberto certo e nada vira receita/despesa', async ({ page, api, checkA11y }) => {
  const acc = await createAccount(api, 'Banco E2E', 100_000)
  const person = await (await api.post('people', { data: { display_name: 'Caio E2E' } })).json()

  await page.goto('/terceiros')
  await page.getByRole('button', { name: 'Novo registro' }).first().click()
  const novo = page.getByRole('dialog', { name: 'Novo registro com terceiro' })
  await novo.getByRole('radio', { name: /Emprestei dinheiro/ }).check()
  await novo.getByLabel('Pessoa', { exact: true }).selectOption(person.id)
  await novo.getByLabel('Valor', { exact: true }).fill('40000')
  await novo.getByLabel('Descrição', { exact: true }).fill('Conserto do carro')
  await novo.getByLabel('Saiu da conta', { exact: true }).selectOption(acc.id)
  await checkA11y(page)
  await novo.getByRole('button', { name: 'Salvar registro' }).click()
  await expect(page.getByText('Registro criado.')).toBeVisible()
  await expect.poll(() => balanceOf(api, acc.id)).toBe(60_000)

  // Recebe R$ 150,00 dos R$ 400,00.
  await page.getByRole('button', { name: 'Registrar recebimento' }).click()
  const acerto = page.getByRole('dialog', { name: 'Registrar recebimento' })
  await acerto.getByLabel('Valor', { exact: true }).fill('15000')
  await acerto.getByLabel('Entrou na conta', { exact: true }).selectOption(acc.id)
  await acerto.getByRole('button', { name: 'Confirmar' }).click()
  await expect(page.getByText('Acerto registrado.')).toBeVisible()
  await expect.poll(() => balanceOf(api, acc.id)).toBe(75_000)

  const summary = (await (await api.get('party-balances')).json()).summary
  expect(summary.receivable_open_cents).toBe(25_000)
  await expect(page.getByText(brl(250)).first()).toBeVisible()
  await checkA11y(page)

  // Empréstimo e acerto não são receita nem despesa.
  await page.goto('/')
  await expect(page.getByRole('link', { name: /Despesas/ }).first()).toContainText(brl(0))
  await expect(page.getByRole('link', { name: /Receitas/ }).first()).toContainText(brl(0))
})
