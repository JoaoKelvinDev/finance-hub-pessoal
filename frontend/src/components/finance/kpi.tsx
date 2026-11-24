import { motion } from 'motion/react'
import { ArrowDownRight, ArrowUpRight, Info, Minus } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { CurrencyDisplay } from '@/components/finance/currency'
import { Tooltip } from '@/components/ui/misc'
import { formatBRL, formatPct } from '@/lib/money'
import { riseItem } from '@/lib/motion'
import { cn } from '@/lib/utils'
import type { Kpi } from '@/types/api'

interface FinancialKpiProps {
  label: string
  kpi: Kpi
  icon: ReactNode
  to?: string
  /** true quando subir é ruim (ex.: despesas). */
  inverse?: boolean
  emphasis?: 'default' | 'warning' | 'danger'
}

export function FinancialKpi({ label, kpi, icon, to, inverse, emphasis = 'default' }: FinancialKpiProps) {
  const change = kpi.change_pct
  const good = change === null ? null : inverse ? change < 0 : change > 0
  const Trend = change === null || change === 0 ? Minus : change > 0 ? ArrowUpRight : ArrowDownRight

  const body = (
    <>
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-[13px] font-medium text-muted">
          <span
            className={cn(
              'grid size-7 place-items-center rounded-lg bg-surface-2 text-fg [&_svg]:size-4',
              emphasis === 'warning' && 'bg-warning-soft text-warning',
              emphasis === 'danger' && 'bg-negative-soft text-negative',
            )}
            aria-hidden
          >
            {icon}
          </span>
          {label}
        </span>
        <Tooltip content={kpi.formula}>
          <span
            role="button"
            tabIndex={0}
            onClick={(e) => e.preventDefault()}
            className="grid size-6 place-items-center rounded-md text-muted/70 hover:text-fg"
            aria-label={`Como é calculado: ${kpi.formula}`}
          >
            <Info className="size-3.5" />
          </span>
        </Tooltip>
      </div>
      <CurrencyDisplay cents={kpi.value_cents} className="mt-3 block text-[22px] font-semibold tracking-tight" />
      <div className="mt-1 h-5 text-xs">
        {kpi.previous_cents !== null && (
          <span className="flex items-center gap-1 text-muted">
            <span
              className={cn(
                'inline-flex items-center gap-0.5 font-medium',
                good === true && 'text-positive',
                good === false && 'text-negative',
              )}
            >
              <Trend className="size-3.5" aria-hidden />
              {formatPct(change)}
            </span>
            <span className="truncate">vs. {formatBRL(kpi.previous_cents)} no período anterior</span>
          </span>
        )}
      </div>
    </>
  )

  return (
    <motion.div variants={riseItem}>
      {to ? (
        <Link
          to={to}
          className="group block h-full rounded-xl border border-border bg-surface p-4 shadow-card transition-[border-color,box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-pop"
        >
          {body}
        </Link>
      ) : (
        <div className="h-full rounded-xl border border-border bg-surface p-4 shadow-card">{body}</div>
      )}
    </motion.div>
  )
}
