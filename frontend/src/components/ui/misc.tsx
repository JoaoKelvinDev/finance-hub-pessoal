import { Tooltip as T } from 'radix-ui'
import { motion } from 'motion/react'
import type { ReactNode } from 'react'
import { spring } from '@/lib/motion'
import { cn } from '@/lib/utils'

export function Badge({ children, variant = 'default', className }: { children: ReactNode; variant?: 'default' | 'outline' | 'destructive'; className?: string }) {
  const variants = {
    default: 'bg-accent/10 text-accent border-accent/20',
    outline: 'border-border bg-transparent',
    destructive: 'bg-negative/10 text-negative border-negative/20',
  }
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium',
        variants[variant],
        className,
      )}
    >
      {children}
    </span>
  )
}

export function Tooltip({ content, children }: { content: ReactNode; children: ReactNode }) {
  return (
    <T.Root delayDuration={200}>
      <T.Trigger asChild>{children}</T.Trigger>
      <T.Portal>
        <T.Content
          sideOffset={6}
          className="z-50 max-w-72 rounded-lg border border-border bg-fg px-3 py-2 text-xs leading-relaxed text-bg shadow-pop"
        >
          {content}
        </T.Content>
      </T.Portal>
    </T.Root>
  )
}

interface SegmentedProps<V extends string> {
  value: V
  onChange: (v: V) => void
  options: { value: V; label: string }[]
  layoutId: string
  className?: string
  label: string
}

/** Abas segmentadas com indicador deslizante compartilhado (layoutId). */
export function Segmented<V extends string>({ value, onChange, options, layoutId, className, label }: SegmentedProps<V>) {
  return (
    <div role="tablist" aria-label={label} className={cn('inline-flex rounded-lg bg-surface-2 p-1', className)}>
      {options.map((o) => {
        const active = o.value === value
        return (
          <button
            key={o.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(o.value)}
            className={cn(
              'relative h-8 rounded-md px-3 text-[13px] font-medium whitespace-nowrap',
              active ? 'text-fg' : 'text-muted hover:text-fg',
            )}
          >
            {active && (
              <motion.span
                layoutId={layoutId}
                className="absolute inset-0 rounded-md bg-surface shadow-card"
                transition={spring}
              />
            )}
            <span className="relative">{o.label}</span>
          </button>
        )
      })}
    </div>
  )
}
