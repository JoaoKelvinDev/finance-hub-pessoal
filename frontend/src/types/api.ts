export type AccountType = 'CHECKING' | 'SAVINGS' | 'CASH' | 'DIGITAL_WALLET' | 'OTHER'
export type TxKind = 'INCOME' | 'EXPENSE' | 'TRANSFER_IN' | 'TRANSFER_OUT' | 'ADJUSTMENT'
export type TxStatus = 'PLANNED' | 'POSTED' | 'CANCELLED'

export type CardType = 'CREDIT' | 'DEBIT' | 'PREPAID'
export type CardBrand = 'VISA' | 'MASTERCARD' | 'ELO' | 'AMEX' | 'HIPERCARD' | 'OTHER'
export type StatementStatus = 'OPEN' | 'CLOSED' | 'PARTIALLY_PAID' | 'PAID' | 'OVERDUE' | 'CANCELLED'
export type PurchaseStatus = 'ACTIVE' | 'REVERSED' | 'CANCELLED'
export type InstallmentStatus = 'PENDING' | 'POSTED' | 'PAID' | 'REVERSED' | 'CANCELLED'
export type PurchaseBoundaryPolicy = 'INCLUSIVE' | 'EXCLUSIVE'
export type BillCategory = 'RENT' | 'WATER' | 'ELECTRICITY' | 'GAS' | 'INTERNET' | 'PHONE' | 'TV' | 'INSURANCE' | 'CONDO' | 'EDUCATION' | 'HEALTH' | 'OTHER'
export type RecurrenceFrequency = 'MONTHLY' | 'BIMONTHLY' | 'QUARTERLY' | 'SEMIANNUAL' | 'ANNUAL' | 'CUSTOM'
export type RecurrenceStatus = 'ACTIVE' | 'PAUSED' | 'ENDED'
export type BillInstallmentStatus = 'PENDING' | 'POSTED' | 'PAID' | 'REVERSED' | 'CANCELLED' | 'SKIPPED'

export interface CreditCard {
  id: string
  name: string
  bank: string | null
  nickname: string | null
  last_four: string | null
  brand: CardBrand | null
  type: CardType
  limit_cents: number
  closing_day: number
  due_day: number
  due_month_offset: number
  purchase_boundary_policy: PurchaseBoundaryPolicy
  default_payment_account_id: string | null
  color: string
  archived_at: string | null
  used_limit_cents: number
  available_limit_cents: number
}

export interface CardStatement {
  id: string
  card_id: string
  cycle_start_date: string
  cycle_end_exclusive: string
  due_date: string
  status: StatementStatus
  paid_cents: number
  total_cents: number
  closed_at: string | null
  cancelled_at: string | null
  cancel_reason: string | null
}

export interface CardPurchase {
  id: string
  card_id: string
  description: string
  merchant: string | null
  purchased_on: string
  total_cents: number
  installments_count: number
  category_id: string | null
  category_name: string | null
  category_color: string | null
  person_id: string | null
  person_name: string | null
  status: PurchaseStatus
  notes: string | null
  created_at: string
}

export interface CardInstallment {
  id: string
  purchase_id: string
  statement_id: string
  installment_number: number
  amount_cents: number
  status: InstallmentStatus
  paid_at: string | null
}

export interface StatementPayment {
  id: string
  statement_id: string
  transaction_id: string
  amount_cents: number
  paid_on: string
}

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

export interface Bill {
  id: string
  name: string
  category: BillCategory
  description: string | null
  account_id: string
  account_name: string | null
  account_color: string | null
  default_amount_cents: number
  color: string
  archived_at: string | null
  notes: string | null
  created_at: string
}

export interface Recurrence {
  id: string
  bill_id: string
  bill_name: string | null
  bill_color: string | null
  frequency: RecurrenceFrequency
  day_of_month: number
  start_date: string
  end_date: string | null
  custom_months_interval: number | null
  auto_post: boolean
  status: RecurrenceStatus
  last_posted_due: string | null
  next_due_date: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface BillInstallment {
  id: string
  bill_id: string
  bill_name: string | null
  bill_color: string | null
  recurrence_id: string | null
  due_date: string
  amount_cents: number
  status: BillInstallmentStatus
  paid_at: string | null
  transaction_id: string | null
  notes: string | null
  created_at: string
}

export interface BillInstallmentPage {
  items: BillInstallment[]
  total: number
  page: number
  limit: number
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
