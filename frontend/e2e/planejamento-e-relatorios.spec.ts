import { readFileSync } from 'node:fs'
import { brl, createAccount, expect, test, todayISO } from './fixtures'

async function expense(api: import('@playwright/test').APIRequestContext, accountId: string, cents: number, category: string) {
  const cats: { id: string; name: string }[] = await (await api.get('categories')).json()
  const r = await api.post('transactions', {
    data: {
      account_id: accountId, kind: 'EXPENSE', amount_cents: cents, effective_date: todayISO(),
      description: `Gasto ${category}`, category_id: cats.find((c) => c.name === category)!.id,
    },
  })
  expect(r.status(), await r.text()).toBe(201)
}

test('orçamento por categoria mostra consumo e alerta a partir de 80%', async ({ page, api, checkA11y }) => {
  const acc = await createAccount(api, 'Banco E2E', 500_000)
  await expense(api, acc.id, 85_000, 'Mercado')

  await page.goto('/planejamento')
  await expect(page.getByText('Nenhum orçamento neste mês')).toBeVisible()
  await page.getByRole('button', { name: 'Novo orçamento' }).click()
  const dlg = page.getByRole('dialog', { name: 'Novo orçamento' })
  await dlg.getByLabel('Categoria').selectOption({ label: 'Alimentação (inteira)' })
  await dlg.getByLabel('Teto do mês').fill('100000')
  await dlg.getByRole('button', { name: 'Criar orçamento' }).click()
  await expect(page.getByText('Orçamento criado.')).toBeVisible()

  // Mercado é subcategoria de Alimentação: R$ 850 de R$ 1.000 = 85%.
  await expect(page.getByText('Alimentação', { exact: true })).toBeVisible()
  await expect(page.getByText(`de ${brl(1000)}`)).toBeVisible()
  await expect(page.getByText(/Atenção: passou de 80% · 85%/)).toBeVisible()
  await expect(page.getByRole('progressbar', { name: '85% usado' })).toBeVisible()
  await checkA11y(page)
})

test('relatório de categorias e exportação em XLSX, PDF e CSV', async ({ page, api, checkA11y }) => {
  const acc = await createAccount(api, 'Banco E2E', 500_000)
  await expense(api, acc.id, 25_050, 'Mercado')
  await expense(api, acc.id, 10_000, 'Delivery')

  await page.goto('/relatorios')
  await expect(page.getByText(brl(350.5)).first()).toBeVisible()
  await checkA11y(page)

  for (const [label, ext, magic] of [
    ['Excel (XLSX)', 'xlsx', 'PK'],
    ['PDF', 'pdf', '%PDF'],
    ['CSV', 'csv', '﻿Categoria;'],
  ] as const) {
    await page.getByRole('button', { name: /Exportar/ }).click()
    const menu = page.getByRole('menu', { name: 'Formato do arquivo' })
    await expect(menu).toBeVisible()
    const [download] = await Promise.all([page.waitForEvent('download'), menu.getByRole('menuitem', { name: new RegExp(label.replace(/[()]/g, '\\$&')) }).click()])
    expect(download.suggestedFilename()).toMatch(new RegExp(`^finance-hub-categories-\\d{8}-\\d{8}\\.${ext}$`))
    const bytes = readFileSync(await download.path())
    expect(bytes.subarray(0, magic.length * 3).toString('utf8').startsWith(magic)).toBe(true)
    if (ext === 'csv') expect(bytes.toString('utf8')).toContain('Total;;350,50;')
    await expect(page.getByText(`Arquivo ${download.suggestedFilename()} baixado.`)).toBeVisible()
  }

  // Menu acessível por teclado: abre, navega com setas e fecha com Esc.
  await page.getByRole('button', { name: /Exportar/ }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('menuitem', { name: /^Excel/ })).toBeFocused()
  await page.keyboard.press('ArrowDown')
  await expect(page.getByRole('menuitem', { name: /^PDF/ })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('menu')).toBeHidden()
  await expect(page.getByRole('button', { name: /Exportar/ })).toBeFocused()
})
