import { CreditCard } from 'lucide-react'
import { contrastInk, initials, resolveBrand, type Brand } from '@/lib/brands'
import { cn } from '@/lib/utils'

const SIZES = {
  sm: { box: 'size-8', icon: 15, text: 'text-[11px]', badge: 'size-4', badgeIcon: 8, badgeText: 'text-[7px]' },
  md: { box: 'size-10', icon: 18, text: 'text-xs', badge: 'size-5', badgeIcon: 10, badgeText: 'text-[8px]' },
}

function Mark({ brand, fallbackName, color, px, textCls }: {
  brand: Brand | null
  fallbackName: string
  color?: string | null
  px: number
  textCls: string
}) {
  if (brand?.icon) {
    return (
      <svg viewBox="0 0 24 24" width={px} height={px} fill={contrastInk(brand.color)} aria-hidden>
        <path d={brand.icon.path} />
      </svg>
    )
  }
  const label = brand?.monogram ?? initials(fallbackName)
  const ink = brand ? contrastInk(brand.color) : color ? '#FFFFFF' : undefined
  return (
    <span className={cn('font-semibold leading-none tracking-tight', textCls)} style={{ color: ink }} aria-hidden>
      {label}
    </span>
  )
}

/**
 * Avatar do estabelecimento (Netflix, iFood…) com selo opcional do cartão/banco usado.
 * Sem marca reconhecida: iniciais sobre a cor da categoria (ou neutro).
 */
export function BrandAvatar({
  name,
  merchant,
  fallbackColor,
  card,
  size = 'md',
  className,
}: {
  /** Descrição da compra/lançamento. */
  name: string
  /** Estabelecimento informado (tem prioridade no reconhecimento). */
  merchant?: string | null
  /** Cor usada quando não há marca (ex.: cor da categoria). */
  fallbackColor?: string | null
  /** Cartão usado: o selo mostra o banco reconhecido ou o ícone de cartão na cor dele. */
  card?: { name: string; bank?: string | null; color?: string | null } | null
  size?: keyof typeof SIZES
  className?: string
}) {
  const s = SIZES[size]
  const brand = resolveBrand(merchant, name)
  const bg = brand ? `#${brand.color}` : fallbackColor ? fallbackColor : undefined
  const cardBrand = card ? resolveBrand(card.bank, card.name) : null
  const label = brand?.label ?? merchant ?? name

  return (
    <span className={cn('relative inline-flex shrink-0', className)} title={card ? `${label} · ${card.name}` : label}>
      <span
        className={cn('grid place-items-center rounded-full ring-1 ring-black/5', s.box, !bg && 'bg-surface-2 text-muted')}
        style={bg ? { background: bg } : undefined}
      >
        <Mark brand={brand} fallbackName={merchant || name} color={bg} px={s.icon} textCls={s.text} />
      </span>
      {card && (
        <span
          className={cn(
            'absolute -right-1 -bottom-1 grid place-items-center rounded-full ring-2 ring-surface',
            s.badge,
          )}
          style={{ background: cardBrand ? `#${cardBrand.color}` : (card.color ?? 'var(--accent)') }}
          aria-hidden
        >
          {cardBrand ? (
            <Mark brand={cardBrand} fallbackName={card.name} px={s.badgeIcon} textCls={s.badgeText} />
          ) : (
            <CreditCard style={{ width: s.badgeIcon, height: s.badgeIcon }} className="text-white" />
          )}
        </span>
      )}
    </span>
  )
}
