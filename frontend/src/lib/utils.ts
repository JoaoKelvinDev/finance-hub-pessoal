import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function newIdempotencyKey() {
  return crypto.randomUUID()
}

export function formatCurrency(cents: number, options: { currency?: string; locale?: string; signed?: boolean } = {}): string {
  return new Intl.NumberFormat(options.locale ?? 'pt-BR', {
    style: 'currency',
    currency: options.currency ?? 'BRL',
    signDisplay: options.signed ? 'always' : 'auto',
  }).format(cents / 100)
}
