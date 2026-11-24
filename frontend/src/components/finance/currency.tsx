import { animate, useReducedMotion } from 'motion/react'
import { forwardRef, useEffect, useRef, useState, type InputHTMLAttributes } from 'react'
import { formatBRL, maskCents } from '@/lib/money'
import { cn } from '@/lib/utils'

interface CurrencyProps {
  cents: number
  className?: string
  signed?: boolean
  /** Colore pelo sinal (entrada verde, saída vermelha). O sinal textual é sempre mostrado. */
  tone?: boolean
  animated?: boolean
}

/** Exibe BRL com números tabulares; anima suavemente entre valores. */
export function CurrencyDisplay({ cents, className, signed, tone, animated = true }: CurrencyProps) {
  const reduce = useReducedMotion()
  const [shown, setShown] = useState(cents)
  const prev = useRef(cents)

  useEffect(() => {
    if (!animated || reduce || prev.current === cents) {
      prev.current = cents
      setShown(cents)
      return
    }
    const controls = animate(prev.current, cents, {
      duration: 0.6,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => setShown(Math.round(v)),
    })
    prev.current = cents
    return () => controls.stop()
  }, [cents, animated, reduce])

  return (
    <span
      className={cn(
        'num',
        tone && cents > 0 && 'text-positive',
        tone && cents < 0 && 'text-negative',
        className,
      )}
    >
      {formatBRL(shown, { signed })}
      <span className="sr-only">{cents < 0 ? ' (saída)' : cents > 0 && tone ? ' (entrada)' : ''}</span>
    </span>
  )
}

interface MoneyInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'value' | 'onChange'> {
  valueCents: number | null
  onChangeCents: (cents: number | null) => void
}

/** Máscara BRL na digitação; o valor real é sempre um inteiro em centavos. */
export const MoneyInput = forwardRef<HTMLInputElement, MoneyInputProps>(
  ({ valueCents, onChangeCents, className, ...props }, ref) => {
    const text = valueCents ? maskCents(String(valueCents)).text : ''
    return (
      <div className="relative">
        <span className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-sm text-muted">R$</span>
        <input
          ref={ref}
          inputMode="numeric"
          autoComplete="off"
          placeholder="0,00"
          value={text}
          onChange={(e) => {
            const { cents } = maskCents(e.target.value)
            onChangeCents(cents || null)
          }}
          className={cn(
            'num h-11 w-full rounded-lg border border-border bg-surface pr-3 pl-10 text-lg font-semibold text-fg shadow-card outline-none transition-[border-color,box-shadow] duration-150 placeholder:text-muted/60 focus:border-accent focus:ring-3 focus:ring-accent/20 aria-invalid:border-negative',
            className,
          )}
          {...props}
        />
      </div>
    )
  },
)
MoneyInput.displayName = 'MoneyInput'
