import { motion } from 'motion/react'
import { CreditCard } from 'lucide-react'
import type { ReactNode } from 'react'
import { CurrencyDisplay, MoneyInput as CurrencyInput } from './currency'
import { cn } from '@/lib/utils'

export { CurrencyDisplay, CurrencyInput }

interface CardUtilizationProps {
  used: number
  limit: number
  color?: string
  className?: string
  children?: ReactNode
}

export function CardUtilization({ used, limit, color = '#3B82F6', className, children }: CardUtilizationProps) {
  const available = limit - used
  const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0
  const isWarning = pct >= 80
  const isDanger = pct >= 100

  return (
    <div className={cn('space-y-3', className)}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className="grid size-8 place-items-center rounded-xl"
            style={{ background: `${color}15` }}
            aria-hidden
          >
            <CreditCard className="size-4" style={{ color }} />
          </span>
          <div>
            <p className="text-sm font-medium text-fg">Limite do cartão</p>
            <p className="text-xs text-muted">
              {pct.toFixed(1)}% utilizado {available < 0 ? '· limite excedido' : `· ${new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(available / 100)} disponível`}
            </p>
          </div>
        </div>
        <CurrencyDisplay cents={used} className={cn('text-lg font-semibold', isWarning && 'text-warning', isDanger && 'text-negative')} />
      </div>

      <div className="relative h-2.5 rounded-full bg-surface-2 overflow-hidden" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} aria-label={`Utilização do limite: ${pct.toFixed(1)}%`}>
        <motion.div
          className="h-full rounded-full transition-all duration-500 ease-out"
          style={{
            width: `${Math.min(pct, 100)}%`,
            background: isDanger
              ? 'linear-gradient(90deg, #EF4444, #F87171)'
              : isWarning
              ? 'linear-gradient(90deg, #F59E0B, #FBBF24)'
              : `linear-gradient(90deg, ${color}, ${color}CC)`,
          }}
          initial={{ width: 0 }}
          animate={{ width: `${Math.min(pct, 100)}%` }}
        />
        {pct > 100 && (
          <motion.div
            className="absolute top-0 right-0 h-full w-4 bg-gradient-to-l from-transparent to-negative/30"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          />
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-muted">
        <span>R$ 0</span>
        <span>{new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(limit / 100)}</span>
      </div>

      {children && <div className="pt-2 border-t border-border">{children}</div>}
    </div>
  )
}

interface UtilizationBadgeProps {
  used: number
  limit: number
  color?: string
  size?: 'sm' | 'md'
}

export function UtilizationBadge({ used, limit, color = '#3B82F6', size = 'md' }: UtilizationBadgeProps) {
  const available = limit - used
  const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0
  const isWarning = pct >= 80
  const isDanger = pct >= 100

  const configs = {
    sm: { h: 4, px: 2, text: 'text-xs', gap: 1 },
    md: { h: 6, px: 2.5, text: 'text-sm', gap: 1.5 },
  }
  const c = configs[size]

  return (
    <div
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border font-medium',
        `h-${c.h} px-${c.px} ${c.text}`,
        isDanger
          ? 'border-negative/30 bg-negative/10 text-negative'
          : isWarning
          ? 'border-warning/30 bg-warning/10 text-warning'
          : 'border-border bg-surface-2 text-muted',
      )}
    >
      <span className="relative flex items-center gap-1" style={{ color }}>
        <CreditCard className="size-3" aria-hidden />
        {pct.toFixed(0)}%
      </span>
      <span className="text-[11px] text-muted/70">{new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }).format(available / 100)} livre</span>
    </div>
  )
}