import { AnimatePresence, motion } from 'motion/react'
import { BarChart3, Table2 } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useTheme } from '@/app/theme'
import { formatDate, formatMonth, formatShortDate } from '@/lib/date'
import { formatBRL, formatCompactBRL, formatPct } from '@/lib/money'
import { cn } from '@/lib/utils'
import type { CashFlowReport, Dashboard, Projection } from '@/types/api'

// Paleta categórica validada (dataviz): passo claro -> passo escuro do mesmo slot.
const DARK_STEP: Record<string, string> = {
  '#2A78D6': '#3987E5',
  '#EB6834': '#D95926',
  '#1BAF7A': '#199E70',
  '#EDA100': '#C98500',
  '#E87BA4': '#D55181',
  '#008300': '#0CA30C',
  '#6250D6': '#9085E9',
}
const SLOT_ORDER = Object.keys(DARK_STEP)

function seriesColor(hex: string, dark: boolean) {
  const key = hex.toUpperCase()
  return dark ? (DARK_STEP[key] ?? hex) : hex
}

const axis = { fontSize: 11, fill: 'var(--muted)' }
const ANIM = { animationDuration: 650, animationEasing: 'ease-out' as const }

/** Moldura com alternância gráfico/tabela (números nunca dependem só do gráfico). */
export function ChartFrame({
  title,
  description,
  table,
  children,
  legend,
}: {
  title: string
  description?: string
  table: ReactNode
  children: ReactNode
  legend?: ReactNode
}) {
  const [asTable, setAsTable] = useState(false)
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start justify-between gap-3 px-5 pt-4 pb-2">
        <div>
          <h2 className="text-[15px] font-semibold tracking-tight">{title}</h2>
          {description && <p className="mt-0.5 text-[13px] text-muted">{description}</p>}
        </div>
        <button
          onClick={() => setAsTable((v) => !v)}
          className="grid size-8 shrink-0 place-items-center rounded-lg text-muted transition-colors hover:bg-surface-2 hover:text-fg"
          aria-label={asTable ? 'Ver como gráfico' : 'Ver como tabela'}
          aria-pressed={asTable}
          title={asTable ? 'Ver como gráfico' : 'Ver como tabela'}
        >
          {asTable ? <BarChart3 className="size-4" /> : <Table2 className="size-4" />}
        </button>
      </div>
      {legend && !asTable && <div className="px-5">{legend}</div>}
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={asTable ? 'table' : 'chart'}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1, transition: { duration: 0.2 } }}
          exit={{ opacity: 0, transition: { duration: 0.12 } }}
          className="flex-1 px-2 pb-3"
        >
          {asTable ? <div className="max-h-72 overflow-auto px-3">{table}</div> : children}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}

function TipBox({ title, rows }: { title: string; rows: { label: string; value: string; color?: string; dashed?: boolean }[] }) {
  return (
    <div className="min-w-44 rounded-xl border border-border bg-surface/95 px-3 py-2.5 text-xs shadow-pop backdrop-blur">
      <p className="mb-1.5 font-medium text-fg">{title}</p>
      {rows.map((r) => (
        <div key={r.label} className="flex items-center justify-between gap-4 py-0.5">
          <span className="flex items-center gap-1.5 text-muted">
            {r.color && (
              <span
                className={cn('h-2 w-3 rounded-sm', r.dashed && 'border-t-2 border-dashed bg-transparent')}
                style={r.dashed ? { borderColor: r.color } : { background: r.color }}
                aria-hidden
              />
            )}
            {r.label}
          </span>
          <span className="num font-medium text-fg">{r.value}</span>
        </div>
      ))}
    </div>
  )
}

function LegendItem({ color, label, dashed }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted">
      <span
        className={cn('h-2.5 w-3.5 rounded-sm', dashed && 'h-0 rounded-none border-t-2 border-dashed')}
        style={dashed ? { borderColor: color } : { background: color }}
        aria-hidden
      />
      {label}
    </span>
  )
}

const th = 'py-2 pr-3 text-left text-xs font-medium text-muted'
const td = 'num py-2 pr-3 text-sm'

// ---------- Receitas x despesas ----------
export function IncomeExpenseChart({ data }: { data: Dashboard['monthly'] }) {
  const rows = data.map((d) => ({ ...d, label: formatMonth(d.month) + (d.partial ? '*' : '') }))
  const hasData = data.some((d) => d.income_cents || d.expense_cents)
  return (
    <ChartFrame
      title="Receitas × despesas"
      description="Últimos 6 meses, regime de caixa. * mês em andamento (parcial)."
      legend={
        <div className="flex gap-4">
          <LegendItem color="var(--positive)" label="Receitas" />
          <LegendItem color="var(--negative)" label="Despesas" />
        </div>
      }
      table={
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className={th}>Mês</th>
              <th className={th}>Receitas</th>
              <th className={th}>Despesas</th>
              <th className={th}>Saldo líquido</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.month} className="border-b border-border/60">
                <td className="py-2 pr-3 text-sm">{r.label}</td>
                <td className={td}>{formatBRL(r.income_cents)}</td>
                <td className={td}>{formatBRL(r.expense_cents)}</td>
                <td className={td}>{formatBRL(r.net_cents, { signed: true })}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      {hasData ? (
        <div className="h-60">
          <ResponsiveContainer>
            <BarChart data={rows} barGap={2} barCategoryGap="28%" margin={{ top: 12, right: 12, left: 4, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="0" />
              <XAxis dataKey="label" tickLine={false} axisLine={false} tick={axis} />
              <YAxis
                tickLine={false}
                axisLine={false}
                tick={axis}
                width={64}
                tickFormatter={(v: number) => formatCompactBRL(v)}
              />
              <Tooltip
                cursor={{ fill: 'var(--surface-2)', radius: 6 }}
                content={({ active, payload }) =>
                  active && payload?.length ? (
                    <TipBox
                      title={formatMonth(payload[0].payload.month) + (payload[0].payload.partial ? ' (parcial)' : '')}
                      rows={[
                        { label: 'Receitas', value: formatBRL(payload[0].payload.income_cents), color: 'var(--positive)' },
                        { label: 'Despesas', value: formatBRL(payload[0].payload.expense_cents), color: 'var(--negative)' },
                        { label: 'Líquido', value: formatBRL(payload[0].payload.net_cents, { signed: true }) },
                      ]}
                    />
                  ) : null
                }
              />
              <Bar dataKey="income_cents" name="Receitas" fill="var(--positive)" radius={[4, 4, 0, 0]} maxBarSize={22} {...ANIM} />
              <Bar dataKey="expense_cents" name="Despesas" fill="var(--negative)" radius={[4, 4, 0, 0]} maxBarSize={22} {...ANIM} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <ChartEmpty text="Sem receitas ou despesas efetivadas nos últimos 6 meses." />
      )}
    </ChartFrame>
  )
}

// ---------- Evolução do saldo ----------
export function BalanceChart({ data, today }: { data: Dashboard['balance_series']; today: string }) {
  // Duas séries que se encontram em "hoje": realizado (linha cheia) e projeção (tracejada).
  const rows = data.map((p) => ({
    date: p.date,
    real: p.projected ? null : p.balance_cents,
    proj: p.projected || p.date === today ? p.balance_cents : null,
  }))
  const hasProjection = data.some((p) => p.projected)
  return (
    <ChartFrame
      title="Evolução do saldo"
      description={hasProjection ? 'Realizado até hoje; depois, a projeção base (faturas, contas da casa, previsões e terceiros).' : 'Saldo diário das contas ativas.'}
      legend={
        <div className="flex gap-4">
          <LegendItem color="var(--accent)" label="Realizado" />
          {hasProjection && <LegendItem color="var(--accent)" label="Projeção (estimativa)" dashed />}
        </div>
      }
      table={
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className={th}>Data</th>
              <th className={th}>Saldo</th>
              <th className={th}>Tipo</th>
            </tr>
          </thead>
          <tbody>
            {data
              .filter((_, i) => i % Math.max(1, Math.ceil(data.length / 40)) === 0 || i === data.length - 1)
              .map((p) => (
                <tr key={p.date} className="border-b border-border/60">
                  <td className={td}>{formatDate(p.date)}</td>
                  <td className={td}>{formatBRL(p.balance_cents)}</td>
                  <td className="py-2 text-sm text-muted">{p.projected ? 'Projetado' : 'Realizado'}</td>
                </tr>
              ))}
          </tbody>
        </table>
      }
    >
      {data.length ? (
        <div className="h-72">
          <ResponsiveContainer>
            <AreaChart data={rows} margin={{ top: 12, right: 12, left: 4, bottom: 0 }}>
              <defs>
                <linearGradient id="fh-balance" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.4} />
                  <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} stroke="var(--border)" />
              <XAxis
                dataKey="date"
                tickLine={false}
                axisLine={false}
                tick={axis}
                minTickGap={28}
                tickFormatter={formatShortDate}
              />
              <YAxis tickLine={false} axisLine={false} tick={axis} width={64} tickFormatter={(v: number) => formatCompactBRL(v)} />
              <Tooltip
                cursor={{ stroke: 'var(--accent)', strokeWidth: 1, strokeDasharray: '4 4' }}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null
                  const p = payload[0].payload as (typeof rows)[number]
                  const projected = p.real === null
                  return (
                    <TipBox
                      title={formatDate(p.date)}
                      rows={[
                        {
                          label: projected ? 'Saldo projetado' : 'Saldo',
                          value: formatBRL((p.real ?? p.proj) as number),
                          color: 'var(--accent)',
                          dashed: projected,
                        },
                      ]}
                    />
                  )
                }}
              />
              <Area
                type="monotone"
                dataKey="real"
                stroke="var(--accent)"
                strokeWidth={2}
                fill="url(#fh-balance)"
                connectNulls={false}
                activeDot={{ r: 6, strokeWidth: 3, stroke: 'var(--surface)', fill: 'var(--accent)' }}
                {...ANIM}
              />
              {hasProjection && (
                <Area
                  type="monotone"
                  dataKey="proj"
                  stroke="var(--accent)"
                  strokeWidth={2}
                  strokeDasharray="5 4"
                  fill="none"
                  connectNulls={false}
                  activeDot={{ r: 6, strokeWidth: 3, stroke: 'var(--surface)', fill: 'var(--accent)' }}
                  {...ANIM}
                />
              )}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <ChartEmpty text="Cadastre uma conta para acompanhar a evolução do saldo." />
      )}
    </ChartFrame>
  )
}

// ---------- Despesas por categoria ----------
export function CategoryChart({ data }: { data: Dashboard['expenses_by_category'] }) {
  const { dark } = useTheme()
  const [active, setActive] = useState<string | null>(null)
  // Fatias na ordem fixa da paleta: só pares adjacentes validados se tocam. O ranking fica na lista.
  const slices = [...data].sort((a, b) => slot(a.color) - slot(b.color))
  const total = data.reduce((s, d) => s + d.amount_cents, 0)
  const key = (d: (typeof data)[number]) => d.category_id ?? d.name

  const ranking = (
    <ul className="space-y-1">
      {data.map((d) => (
        <li
          key={key(d)}
          onMouseEnter={() => setActive(key(d))}
          onMouseLeave={() => setActive(null)}
          className={cn(
            'flex items-center gap-2 rounded-lg px-2 py-1.5 transition-colors',
            active === key(d) && 'bg-surface-2',
          )}
        >
          <span className="size-2.5 shrink-0 rounded-sm" style={{ background: seriesColor(d.color, dark) }} aria-hidden />
          <span className="min-w-0 flex-1 truncate text-sm">{d.name}</span>
          <span className="num text-xs text-muted">{d.share_pct.toLocaleString('pt-BR')}%</span>
          <span className="num w-24 text-right text-sm font-medium">{formatBRL(d.amount_cents)}</span>
        </li>
      ))}
    </ul>
  )

  return (
    <ChartFrame
      title="Despesas por categoria"
      description="Categorias principais no período; 5 maiores e as demais agrupadas."
      table={
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className={th}>Categoria</th>
              <th className={th}>Valor</th>
              <th className={th}>Participação</th>
              <th className={th}>Vs. anterior</th>
            </tr>
          </thead>
          <tbody>
            {data.map((d) => (
              <tr key={key(d)} className="border-b border-border/60">
                <td className="py-2 pr-3 text-sm">{d.name}</td>
                <td className={td}>{formatBRL(d.amount_cents)}</td>
                <td className={td}>{d.share_pct.toLocaleString('pt-BR')}%</td>
                <td className={td}>{formatPct(d.change_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      }
    >
      {data.length ? (
        <div className="@container"><div className="grid items-center gap-3 px-3 @lg:grid-cols-[180px_1fr]">
          <div className="relative mx-auto size-44">
            <ResponsiveContainer>
              <PieChart>
                <Pie
                  data={slices}
                  dataKey="amount_cents"
                  nameKey="name"
                  innerRadius="66%"
                  outerRadius="100%"
                  paddingAngle={1.5}
                  stroke="var(--surface)"
                  strokeWidth={2}
                  cornerRadius={3}
                  startAngle={90}
                  endAngle={-270}
                  onMouseEnter={(_, i) => setActive(key(slices[i]))}
                  onMouseLeave={() => setActive(null)}
                  {...ANIM}
                >
                  {slices.map((d) => (
                    <Cell
                      key={key(d)}
                      fill={seriesColor(d.color, dark)}
                      opacity={active && active !== key(d) ? 0.35 : 1}
                      style={{ transition: 'opacity 180ms ease-out', outline: 'none' }}
                    />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
              <div>
                <p className="text-[11px] text-muted">Total</p>
                <p className="num text-sm font-semibold">{formatBRL(total)}</p>
              </div>
            </div>
          </div>
          {ranking}
        </div></div>
      ) : (
        <ChartEmpty text="Nenhuma despesa efetivada no período." />
      )}
    </ChartFrame>
  )
}

// ---------- Minigráfico dos KPIs ----------
export interface SparkPoint {
  label: string
  value: number
}

/** Linha fina de tendência para os cartões de KPI (sem eixos; tooltip com o valor do ponto). */
export function Sparkline({ points, tone, id }: { points: SparkPoint[]; tone: 'positive' | 'negative' | 'accent'; id: string }) {
  if (points.length < 2) return <div className="h-12" aria-hidden />
  const color = `var(--${tone})`
  return (
    <div className="h-12" role="img" aria-label={`Tendência: de ${formatBRL(points[0].value)} a ${formatBRL(points[points.length - 1].value)}`}>
      <ResponsiveContainer>
        <AreaChart data={points} margin={{ top: 4, right: 2, left: 2, bottom: 2 }}>
          <defs>
            <linearGradient id={`spark-${id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.28} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <YAxis hide domain={['dataMin', 'dataMax']} />
          <Tooltip
            cursor={{ stroke: 'var(--muted)', strokeWidth: 1, strokeDasharray: '2 3' }}
            content={({ active, payload }) =>
              active && payload?.length ? (
                <div className="rounded-md border border-border bg-surface px-2 py-1 text-[11px] shadow-pop">
                  <span className="text-muted">{(payload[0].payload as SparkPoint).label}: </span>
                  <span className="num font-medium">{formatBRL((payload[0].payload as SparkPoint).value)}</span>
                </div>
              ) : null
            }
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            fill={`url(#spark-${id})`}
            activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface)' }}
            {...ANIM}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

function slot(hex: string) {
  const i = SLOT_ORDER.indexOf(hex.toUpperCase())
  return i === -1 ? 99 : i
}

function ChartEmpty({ text }: { text: string }) {
  return <div className="grid h-60 place-items-center px-6 text-center text-sm text-muted">{text}</div>
}

// ---------- Projeção 30/60/90 ----------
/** Duas linhas na mesma escala (saldo em R$): cenário base e conservador. */
export function ProjectionChart({ data }: { data: Projection }) {
  const rows = data.points
  const lowest = data.conservative.lowest_date
  return (
    <ChartFrame
      title="Saldo projetado"
      description={`Próximos ${data.days} dias. Estimativa com o que está cadastrado, não saldo garantido.`}
      legend={
        <div className="flex flex-wrap gap-4">
          <LegendItem color="var(--accent)" label="Base (inclui recorrências e valores a receber de terceiros)" />
          <LegendItem color="var(--muted)" label="Conservador (só obrigações e receitas já lançadas)" dashed />
        </div>
      }
      table={
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className={th}>Data</th>
              <th className={th}>Base</th>
              <th className={th}>Conservador</th>
            </tr>
          </thead>
          <tbody>
            {rows
              .filter((_, i) => i % Math.max(1, Math.ceil(rows.length / 30)) === 0 || i === rows.length - 1)
              .map((p) => (
                <tr key={p.date} className="border-b border-border/60">
                  <td className={td}>{formatDate(p.date)}</td>
                  <td className={td}>{formatBRL(p.base_cents)}</td>
                  <td className={td}>{formatBRL(p.conservative_cents)}</td>
                </tr>
              ))}
          </tbody>
        </table>
      }
    >
      <div className="h-72">
        <ResponsiveContainer>
          <AreaChart data={rows} margin={{ top: 12, right: 12, left: 4, bottom: 0 }}>
            <defs>
              <linearGradient id="fh-proj" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--accent)" stopOpacity={0.35} />
                <stop offset="100%" stopColor="var(--accent)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke="var(--border)" />
            <XAxis dataKey="date" tickLine={false} axisLine={false} tick={axis} minTickGap={32} tickFormatter={formatShortDate} />
            <YAxis tickLine={false} axisLine={false} tick={axis} width={64} tickFormatter={(v: number) => formatCompactBRL(v)} />
            <ReferenceLine y={0} stroke="var(--negative)" strokeDasharray="3 3" strokeOpacity={0.6} />
            <ReferenceDot x={lowest} y={data.conservative.lowest_cents} r={5} fill="var(--warning)" stroke="var(--surface)" strokeWidth={2} />
            <Tooltip
              cursor={{ stroke: 'var(--accent)', strokeWidth: 1, strokeDasharray: '4 4' }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null
                const p = payload[0].payload as (typeof rows)[number]
                return (
                  <TipBox
                    title={formatDate(p.date)}
                    rows={[
                      { label: 'Base', value: formatBRL(p.base_cents), color: 'var(--accent)' },
                      { label: 'Conservador', value: formatBRL(p.conservative_cents), color: 'var(--muted)', dashed: true },
                    ]}
                  />
                )
              }}
            />
            <Area type="stepAfter" dataKey="base_cents" stroke="var(--accent)" strokeWidth={2} fill="url(#fh-proj)"
              activeDot={{ r: 5, strokeWidth: 3, stroke: 'var(--surface)', fill: 'var(--accent)' }} {...ANIM} />
            <Area type="stepAfter" dataKey="conservative_cents" stroke="var(--muted)" strokeWidth={2} strokeDasharray="5 4"
              fill="none" activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--surface)' }} {...ANIM} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </ChartFrame>
  )
}

// ---------- Fluxo de caixa (relatório) ----------
/** Receitas e despesas por período, lado a lado (mesma unidade, um eixo só). */
export function CashFlowChart({ data }: { data: CashFlowReport }) {
  const label = (p: string) => (data.granularity === 'day' ? formatShortDate(p) : formatMonth(p))
  const rows = data.points.map((p) => ({ ...p, label: label(p.period) }))
  const hasData = rows.some((r) => r.income_cents || r.expense_cents)
  return (
    <ChartFrame
      title="Receitas × despesas"
      description={`Efetivadas, por ${data.granularity === 'day' ? 'dia' : 'mês'}. Transferências, empréstimos e acertos não entram.`}
      legend={
        <div className="flex gap-4">
          <LegendItem color="var(--positive)" label="Receitas" />
          <LegendItem color="var(--negative)" label="Despesas" />
        </div>
      }
      table={
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className={th}>Período</th>
              <th className={th}>Receitas</th>
              <th className={th}>Despesas</th>
              <th className={th}>Resultado</th>
            </tr>
          </thead>
          <tbody>
            {rows
              .filter((r) => r.income_cents || r.expense_cents)
              .map((r) => (
                <tr key={r.period} className="border-b border-border/60">
                  <td className="py-2 pr-3 text-sm">{r.label}</td>
                  <td className={td}>{formatBRL(r.income_cents)}</td>
                  <td className={td}>{formatBRL(r.expense_cents)}</td>
                  <td className={td}>{formatBRL(r.net_cents, { signed: true })}</td>
                </tr>
              ))}
          </tbody>
        </table>
      }
    >
      {hasData ? (
        <div className="h-72">
          <ResponsiveContainer>
            <BarChart data={rows} barGap={2} barCategoryGap="24%" margin={{ top: 12, right: 12, left: 4, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="var(--border)" />
              <XAxis dataKey="label" tickLine={false} axisLine={false} tick={axis} minTickGap={16} />
              <YAxis tickLine={false} axisLine={false} tick={axis} width={64} tickFormatter={(v: number) => formatCompactBRL(v)} />
              <Tooltip
                cursor={{ fill: 'var(--surface-2)', radius: 6 }}
                content={({ active, payload }) =>
                  active && payload?.length ? (
                    <TipBox
                      title={(payload[0].payload as (typeof rows)[number]).label}
                      rows={[
                        { label: 'Receitas', value: formatBRL(payload[0].payload.income_cents), color: 'var(--positive)' },
                        { label: 'Despesas', value: formatBRL(payload[0].payload.expense_cents), color: 'var(--negative)' },
                        { label: 'Resultado', value: formatBRL(payload[0].payload.net_cents, { signed: true }) },
                      ]}
                    />
                  ) : null
                }
              />
              <Bar dataKey="income_cents" fill="var(--positive)" radius={[4, 4, 0, 0]} maxBarSize={20} {...ANIM} />
              <Bar dataKey="expense_cents" fill="var(--negative)" radius={[4, 4, 0, 0]} maxBarSize={20} {...ANIM} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <ChartEmpty text="Sem receitas ou despesas efetivadas no período." />
      )}
    </ChartFrame>
  )
}
