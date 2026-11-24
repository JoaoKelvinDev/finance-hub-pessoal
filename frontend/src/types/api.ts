export type AccountType = 'CHECKING' | 'SAVINGS' | 'CASH' | 'DIGITAL_WALLET' | 'OTHER'
export type TxKind = 'INCOME' | 'EXPENSE' | 'TRANSFER_IN' | 'TRANSFER_OUT' | 'ADJUSTMENT'
export type TxStatus = 'PLANNED' | 'POSTED' | 'CANCELLED'

export interface Account {
  id: string
  name: string
  type: AccountType
  institution: string | null
  color: string
  currency: string
  opening_balance_cents: number
  opening_date: string
  notes: string | null
  archived_at: string | null
  balance_cents: number
  planned_balance_cents: number
}

export interface Category {
  id: string
  parent_id: string | null
  name: string
  kind: 'INCOME' | 'EXPENSE'
  color: string
  archived_at: string | null
}

export interface Person {
  id: string
  display_name: string
  contact: string | null
  notes: string | null
  archived_at: string | null
}

export interface Transaction {
  id: string
  account_id: string
  account_name: string
  amount_cents: number
  kind: TxKind
  status: TxStatus
  effective_date: string
  description: string
  category_id: string | null
  category_name: string | null
  category_color: string | null
  counterparty_id: string | null
  counterparty_name: string | null
  transfer_group_id: string | null
  notes: string | null
  cancel_reason: string | null
  created_at: string
}

export interface TransactionPage {
  items: Transaction[]
  totals: { income_cents: number; expense_cents: number; net_cents: number; count: number }
  total: number
  page: number
  limit: number
}

export interface Ledger {
  account: Account
  items: Transaction[]
  total: number
  page: number
  limit: number
}

export interface Kpi {
  value_cents: number
  previous_cents: number | null
  change_pct: number | null
  formula: string
}

export interface Dashboard {
  period_from: string
  period_to: string
  today: string
  timezone: string
  kpis: Record<'available_balance' | 'income' | 'expense' | 'net' | 'due_soon' | 'overdue' | 'projected', Kpi>
  free_after_commitments_cents: number
  free_until: string
  monthly: { month: string; income_cents: number; expense_cents: number; net_cents: number; partial: boolean }[]
  balance_series: { date: string; balance_cents: number; projected: boolean }[]
  expenses_by_category: {
    category_id: string | null
    name: string
    color: string
    amount_cents: number
    share_pct: number
    previous_cents: number
    change_pct: number | null
  }[]
  upcoming: Transaction[]
  recent: Transaction[]
  accounts: Account[]
  health: { savings_rate_pct: number | null; overdue_count: number; overdue_cents: number }
}

export interface ApiErrorBody {
  error: { code: string; message: string; details: unknown; request_id: string | null }
}
