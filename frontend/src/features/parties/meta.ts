import { AlertTriangle, CheckCircle2, CircleDashed, Clock, XCircle, type LucideIcon } from 'lucide-react'
import { ApiError } from '@/lib/api'
import type { PartyOrigin, PartyStatus } from '@/types/api'

export const ORIGINS: Record<
  PartyOrigin,
  { label: string; short: string; description: string; cash: boolean; direction: 'RECEIVABLE' | 'PAYABLE' }
> = {
  LOAN_GIVEN: {
    label: 'Emprestei dinheiro',
    short: 'Empréstimo concedido',
    description: 'Sai da sua conta e vira um valor a receber. Não conta como despesa.',
    cash: true,
    direction: 'RECEIVABLE',
  },
  ADVANCE: {
    label: 'Paguei algo por alguém',
    short: 'Adiantamento',
    description: 'Você pagou em nome da pessoa e ela vai te reembolsar. Não conta como despesa.',
    cash: true,
    direction: 'RECEIVABLE',
  },
  LOAN_TAKEN: {
    label: 'Peguei emprestado',
    short: 'Empréstimo tomado',
    description: 'Entra na sua conta e vira um valor a devolver. Não conta como receita.',
    cash: true,
    direction: 'PAYABLE',
  },
  OWED_TO_ME: {
    label: 'Alguém me deve',
    short: 'A receber',
    description: 'Valor a receber sem saída de dinheiro agora (ex.: vendi algo fiado).',
    cash: false,
    direction: 'RECEIVABLE',
  },
  I_OWE: {
    label: 'Eu devo a alguém',
    short: 'A pagar',
    description: 'Valor a pagar sem entrada de dinheiro agora (ex.: compra que outra pessoa pagou).',
    cash: false,
    direction: 'PAYABLE',
  },
}

export const PARTY_STATUS: Record<PartyStatus, { label: string; icon: LucideIcon; cls: string }> = {
  OPEN: { label: 'Em aberto', icon: Clock, cls: 'bg-surface-2 text-fg' },
  PARTIALLY_SETTLED: { label: 'Parcial', icon: CircleDashed, cls: 'bg-warning-soft text-warning' },
  OVERDUE: { label: 'Vencido', icon: AlertTriangle, cls: 'bg-negative-soft text-negative' },
  SETTLED: { label: 'Quitado', icon: CheckCircle2, cls: 'bg-positive-soft text-positive' },
  CANCELLED: { label: 'Cancelado', icon: XCircle, cls: 'bg-surface-2 text-muted line-through' },
}

/** Converte erro da API em mensagem geral + erros por campo. */
export function readApiError(err: unknown): { message: string; fields: Record<string, string> } {
  if (err instanceof ApiError) {
    const fields: Record<string, string> = {}
    if (err.code === 'validation_error' && Array.isArray(err.details)) {
      for (const d of err.details as { field: string; message: string }[]) {
        if (d.field) fields[d.field] = d.message.replace(/^Value error, /, '')
      }
      const general = (err.details as { field: string; message: string }[]).find((d) => !d.field)
      if (general) return { message: general.message.replace(/^Value error, /, ''), fields }
    }
    return { message: err.message, fields }
  }
  return { message: 'Não foi possível concluir. Verifique a conexão com a API.', fields: {} }
}
