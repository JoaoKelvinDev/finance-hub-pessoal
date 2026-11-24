import { Monitor, Moon, Plus, Sun } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { useTheme, type ThemePref } from '@/app/theme'
import { ErrorState } from '@/components/finance/states'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, Skeleton } from '@/components/ui/card'
import { Input, Select } from '@/components/ui/field'
import { Segmented } from '@/components/ui/misc'
import { ApiError } from '@/lib/api'
import { useCategories, useCreateCategory } from '@/lib/queries'
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
          <li>Cartões, contas da casa, terceiros e planejamento chegam nas próximas etapas.</li>
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
