import { DatabaseBackup, FileSpreadsheet, Monitor, Moon, Plus, Sun } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { useTheme, type ThemePref } from '@/app/theme'
import { downloadExport } from '@/components/finance/export-button'
import { ErrorState } from '@/components/finance/states'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, Skeleton } from '@/components/ui/card'
import { Input, Select } from '@/components/ui/field'
import { Segmented } from '@/components/ui/misc'
import { ApiError, apiDownload } from '@/lib/api'
import { addDays, todayISO } from '@/lib/date'
import { useAppSettings, useCategories, useCreateCategory, useUpdateSettings } from '@/lib/queries'
import type { Category } from '@/types/api'

export function SettingsPage() {
  const { pref, setPref } = useTheme()
  const [kind, setKind] = useState<'EXPENSE' | 'INCOME'>('EXPENSE')
  const categories = useCategories()
  const roots = categories.data?.filter((c) => c.kind === kind && !c.parent_id) ?? []

  return (
    <div className="mx-auto max-w-[900px] space-y-5">
      <Card>
        <CardHeader title="Aparência" description="Preferência salva neste dispositivo." />
        <div className="flex flex-wrap gap-2 px-5 pb-5">
          {(
            [
              ['system', 'Sistema', Monitor],
              ['light', 'Claro', Sun],
              ['dark', 'Escuro', Moon],
            ] as [ThemePref, string, typeof Sun][]
          ).map(([v, label, Icon]) => (
            <Button key={v} variant={pref === v ? 'primary' : 'secondary'} onClick={() => setPref(v)} aria-pressed={pref === v}>
              <Icon /> {label}
            </Button>
          ))}
        </div>
      </Card>

      <AlertSettingsCard />
      <BundleCard />
      <BackupCard />

      <Card>
        <CardHeader
          title="Categorias"
          description="Subcategorias somam na categoria principal nos gráficos."
          action={
            <Segmented
              label="Tipo de categoria"
              layoutId="cat-kind"
              value={kind}
              onChange={setKind}
              options={[
                { value: 'EXPENSE', label: 'Despesas' },
                { value: 'INCOME', label: 'Receitas' },
              ]}
            />
          }
        />
        {categories.isError ? (
          <ErrorState onRetry={() => categories.refetch()} />
        ) : categories.isLoading ? (
          <div className="space-y-2 px-5 pb-5">
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        ) : (
          <div className="space-y-3 px-5 pb-5">
            {roots.map((r) => (
              <div key={r.id} className="rounded-lg border border-border px-4 py-3">
                <p className="flex items-center gap-2 text-sm font-medium">
                  <span className="size-2.5 rounded-sm" style={{ background: r.color }} aria-hidden />
                  {r.name}
                </p>
                <p className="mt-1 text-xs text-muted">
                  {categories.data!.filter((c) => c.parent_id === r.id).map((c) => c.name).join(' · ') || 'Sem subcategorias'}
                </p>
              </div>
            ))}
            <NewCategory kind={kind} roots={roots} />
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Sobre este aplicativo" />
        <ul className="space-y-1 px-5 pb-5 text-sm text-muted">
          <li>Uso individual: há um único proprietário e nenhum cadastro público.</li>
          <li>Moeda BRL · fuso America/Fortaleza · valores armazenados em centavos.</li>
          <li>Inclui cartões, contas da casa, terceiros, planejamento, relatórios e backup.</li>
        </ul>
      </Card>
    </div>
  )
}

function NewCategory({ kind, roots }: { kind: 'EXPENSE' | 'INCOME'; roots: Category[] }) {
  const create = useCreateCategory()
  const [name, setName] = useState('')
  const [parent, setParent] = useState('')
  return (
    <form
      className="flex flex-wrap gap-2 pt-1"
      onSubmit={async (e) => {
        e.preventDefault()
        if (!name.trim()) return
        try {
          await create.mutateAsync({ name, kind, parent_id: parent || null })
          toast.success(`Categoria “${name}” criada.`)
          setName('')
        } catch (err) {
          toast.error(err instanceof ApiError ? err.message : 'Não foi possível criar.')
        }
      }}
    >
      <Input aria-label="Nome da categoria" placeholder="Nova categoria…" value={name} onChange={(e) => setName(e.target.value)} className="min-w-40 flex-1" maxLength={60} />
      <div className="w-52">
        <Select aria-label="Categoria principal" value={parent} onChange={(e) => setParent(e.target.value)}>
          <option value="">Como categoria principal</option>
          {roots.map((r) => (
            <option key={r.id} value={r.id}>
              Dentro de {r.name}
            </option>
          ))}
        </Select>
      </div>
      <Button type="submit" variant="secondary" loading={create.isPending}>
        <Plus /> Adicionar
      </Button>
    </form>
  )
}

function AlertSettingsCard() {
  const settings = useAppSettings()
  const update = useUpdateSettings()
  const [pct, setPct] = useState<string | null>(null)
  const current = settings.data?.alert_card_utilization_pct
  const value = pct ?? (current !== undefined ? String(current) : '')

  return (
    <Card>
      <CardHeader
        title="Alertas"
        description="Os alertas aparecem no sino do cabeçalho. Lembrete não significa pagamento."
      />
      <form
        className="flex flex-wrap items-end gap-3 px-5 pb-5"
        onSubmit={async (e) => {
          e.preventDefault()
          const n = Number(value)
          if (!Number.isInteger(n) || n < 1 || n > 100) return toast.error('Use um número inteiro de 1 a 100.')
          try {
            await update.mutateAsync({ alert_card_utilization_pct: n })
            setPct(null)
            toast.success('Preferência de alerta salva.')
          } catch (err) {
            toast.error(err instanceof ApiError ? err.message : 'Não foi possível salvar.')
          }
        }}
      >
        <label className="flex flex-col gap-1.5 text-sm font-medium">
          Avisar quando o cartão passar de (% do limite)
          {settings.isPending ? (
            <Skeleton className="h-10 w-28" />
          ) : (
            <Input
              type="number"
              min={1}
              max={100}
              inputMode="numeric"
              className="w-28"
              value={value}
              onChange={(e) => setPct(e.target.value)}
            />
          )}
        </label>
        <Button type="submit" variant="secondary" loading={update.isPending} disabled={pct === null}>
          Salvar
        </Button>
      </form>
    </Card>
  )
}

function BundleCard() {
  const today = todayISO()
  const [from, setFrom] = useState(`${today.slice(0, 8)}01`)
  const [to, setTo] = useState(today)
  const [basis, setBasis] = useState<'CASH' | 'COMPETENCE'>('CASH')
  const [busy, setBusy] = useState(false)
  const presets: [string, () => [string, string]][] = [
    ['Este mês', () => [`${today.slice(0, 8)}01`, today]],
    ['Últimos 3 meses', () => [addDays(today, -90), today]],
    ['Este ano', () => [`${today.slice(0, 4)}-01-01`, today]],
    ['Últimos 12 meses', () => [addDays(today, -365), today]],
  ]
  const invalid = !from || !to || to < from

  return (
    <Card>
      <CardHeader
        title="Pacote completo (Excel)"
        description="Um arquivo XLSX com uma aba para cada relatório e lista do período: lançamentos, compras no cartão, categorias, fluxo de caixa, cartões e terceiros."
      />
      <div className="space-y-4 px-5 pb-5">
        <div className="flex flex-wrap gap-2">
          {presets.map(([label, range]) => {
            const [f, t] = range()
            const active = f === from && t === to
            return (
              <Button
                key={label}
                size="sm"
                variant={active ? 'primary' : 'secondary'}
                aria-pressed={active}
                onClick={() => {
                  setFrom(f)
                  setTo(t)
                }}
              >
                {label}
              </Button>
            )
          })}
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            De
            <Input type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} className="w-44" />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            Até
            <Input type="date" value={to} min={from} onChange={(e) => setTo(e.target.value)} className="w-44" />
          </label>
          <label className="flex flex-col gap-1.5 text-sm font-medium">
            Categorias por
            <div className="w-48">
              <Select value={basis} onChange={(e) => setBasis(e.target.value as 'CASH' | 'COMPETENCE')}>
                <option value="CASH">Regime de caixa</option>
                <option value="COMPETENCE">Regime de competência</option>
              </Select>
            </div>
          </label>
          <Button
            variant="secondary"
            loading={busy}
            disabled={invalid}
            onClick={async () => {
              setBusy(true)
              await downloadExport('/exports/bundle.xlsx', { from, to, basis })
              setBusy(false)
            }}
          >
            <FileSpreadsheet /> Baixar pacote XLSX
          </Button>
        </div>
        {invalid && <p className="text-xs text-negative">A data final deve ser igual ou posterior à inicial.</p>}
        <p className="text-xs text-muted">Período máximo de 2 anos. A exportação fica registrada na auditoria.</p>
      </div>
    </Card>
  )
}

function BackupCard() {
  const [busy, setBusy] = useState(false)
  return (
    <Card>
      <CardHeader
        title="Backup"
        description="Baixa todos os seus dados em um arquivo JSON. Guarde-o em local seguro: ele contém sua vida financeira."
      />
      <div className="space-y-3 px-5 pb-5">
        <Button
          variant="secondary"
          loading={busy}
          onClick={async () => {
            setBusy(true)
            try {
              const name = await apiDownload('/backup')
              toast.success(`Backup ${name} baixado.`)
            } catch (err) {
              toast.error(err instanceof ApiError ? err.message : 'Não foi possível gerar o backup.')
            } finally {
              setBusy(false)
            }
          }}
        >
          <DatabaseBackup /> Baixar backup completo
        </Button>
        <p className="text-xs text-muted">
          Para restaurar, use a linha de comando num banco vazio (nunca sobrescreve dados):{' '}
          <code className="rounded bg-surface-2 px-1.5 py-0.5 text-[11px]">uv run python -m app.cli restore --file backup.json</code>
        </p>
      </div>
    </Card>
  )
}
