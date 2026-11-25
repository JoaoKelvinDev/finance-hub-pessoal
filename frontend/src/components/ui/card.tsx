import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'rounded-2xl border border-border bg-surface bg-gradient-to-b from-white/[0.025] to-transparent shadow-card',
        className,
      )}
      {...props}
    />
  )
}

export function CardHeader({
  title,
  description,
  action,
  children,
  className,
}: {
  title?: ReactNode
  description?: ReactNode
  action?: ReactNode
  children?: ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex items-start justify-between gap-3 px-5 pt-4 pb-3', className)}>
      <div className="min-w-0">
        {title && <h2 className="text-[15px] font-semibold tracking-tight">{title}</h2>}
        {description && <p className="mt-0.5 text-[13px] text-muted">{description}</p>}
        {children}
      </div>
      {action}
    </div>
  )
}

export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('px-5 pb-4', className)} {...props} />
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('shimmer rounded-md', className)} aria-hidden />
}
