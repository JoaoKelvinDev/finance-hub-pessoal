import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type {
  Account,
  Bill,
  BillInstallment,
  CalendarResponse,
  PartyBalanceDetail,
  PartyBalancePage,
  PersonPosition,
  BillInstallmentPage,
  CardInstallment,
  CardPurchase,
  CardStatement,
  Category,
  CreditCard,
  Dashboard,
  Ledger,
  Person,
  Recurrence,
  StatementPayment,
  Transaction,
  TransactionPage,
} from '@/types/api'

export const keys = {
  dashboard: (from: string, to: string) => ['dashboard', from, to] as const,
  accounts: (archived: boolean) => ['accounts', archived] as const,
  ledger: (id: string, page: number) => ['ledger', id, page] as const,
  transactions: (q: object) => ['transactions', q] as const,
  categories: ['categories'] as const,
  people: (archived: boolean) => ['people', archived] as const,
  cards: (archived: boolean) => ['cards', archived] as const,
  card: (id: string) => ['cards', id] as const,
  cardStatements: (cardId: string, status?: string) => ['cards', cardId, 'statements', status] as const,
  statement: (id: string) => ['cards', 'statements', id] as const,
  statementInstallments: (statementId: string) => ['cards', 'statements', statementId, 'installments'] as const,
  cardPurchases: (cardId: string, filters: object) => ['cards', cardId, 'purchases', filters] as const,
  cardUpcoming: (cardId: string, limit: number) => ['cards', cardId, 'upcoming', limit] as const,
  bills: (archived: boolean) => ['bills', archived] as const,
  bill: (id: string) => ['bills', id] as const,
  recurrences: (billId?: string, status?: string) => ['bills', 'recurrences', billId, status] as const,
  recurrence: (id: string) => ['bills', 'recurrences', id] as const,
  billInstallments: (filters: object) => ['bills', 'installments', filters] as const,
  billInstallment: (id: string) => ['bills', 'installments', id] as const,
  upcomingInstallments: (days: number) => ['bills', 'installments', 'upcoming', days] as const,
  overdueInstallments: (limit: number) => ['bills', 'installments', 'overdue', limit] as const,
  calendar: (from: string, to: string) => ['calendar', from, to] as const,
  parties: (q: object) => ['parties', q] as const,
  party: (id: string) => ['parties', 'detail', id] as const,
  personPosition: (id: string) => ['parties', 'person', id] as const,
}

export function useCalendar(from: string, to: string) {
  return useQuery({
    queryKey: keys.calendar(from, to),
    queryFn: ({ signal }) => api<CalendarResponse>('/calendar', { query: { from, to }, signal }),
    placeholderData: keepPreviousData,
  })
}

export function useDashboard(from: string, to: string) {
  return useQuery({
    queryKey: keys.dashboard(from, to),
    queryFn: ({ signal }) => api<Dashboard>('/dashboard', { query: { from, to }, signal }),
    placeholderData: keepPreviousData,
  })
}

export function useAccounts(includeArchived = false) {
  return useQuery({
    queryKey: keys.accounts(includeArchived),
    queryFn: ({ signal }) =>
      api<Account[]>('/accounts', { query: { include_archived: includeArchived }, signal }),
  })
}

export function useLedger(id: string, page: number) {
  return useQuery({
    queryKey: keys.ledger(id, page),
    queryFn: ({ signal }) => api<Ledger>(`/accounts/${id}/ledger`, { query: { page, limit: 30 }, signal }),
    placeholderData: keepPreviousData,
  })
}

export interface TxFilters {
  from?: string
  to?: string
  group?: 'all' | 'income' | 'expense' | 'transfer'
  status?: string
  account_id?: string
  category_id?: string
  q?: string
  page?: number
}

export function useTransactions(filters: TxFilters) {
  return useQuery({
    queryKey: keys.transactions(filters),
    queryFn: ({ signal }) =>
      api<TransactionPage>('/transactions', { query: { ...filters, limit: 30 } as never, signal }),
    placeholderData: keepPreviousData,
  })
}

export function useCategories() {
  return useQuery({
    queryKey: keys.categories,
    queryFn: ({ signal }) => api<Category[]>('/categories', { signal }),
    staleTime: 5 * 60_000,
  })
}

export function usePeople(includeArchived = false) {
  return useQuery({
    queryKey: keys.people(includeArchived),
    queryFn: ({ signal }) =>
      api<Person[]>('/people', { query: { include_archived: includeArchived }, signal }),
  })
}

/** Toda mutação financeira invalida o que depende de saldo. */
function useFinanceMutation<TVars, TOut>(fn: (v: TVars) => Promise<TOut>) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      for (const k of ['dashboard', 'accounts', 'ledger', 'transactions', 'cards', 'bills', 'calendar', 'parties']) {
        void qc.invalidateQueries({ queryKey: [k] })
      }
    },
  })
}

export const useCreateTransaction = () =>
  useFinanceMutation((body: Record<string, unknown>) =>
    api<Transaction>('/transactions', { method: 'POST', body }),
  )

export const useCreateTransfer = () =>
  useFinanceMutation((body: Record<string, unknown>) => api('/transfers', { method: 'POST', body }))

export const useCancelTransaction = () =>
  useFinanceMutation(({ id, reason }: { id: string; reason: string }) =>
    api<Transaction>(`/transactions/${id}/cancel`, { method: 'POST', body: { reason } }),
  )

export const usePostTransaction = () =>
  useFinanceMutation((id: string) => api<Transaction>(`/transactions/${id}/post`, { method: 'POST', body: {} }))

export const useCreateAccount = () =>
  useFinanceMutation((body: Record<string, unknown>) => api<Account>('/accounts', { method: 'POST', body }))

export const useUpdateAccount = () =>
  useFinanceMutation(({ id, ...body }: { id: string } & Record<string, unknown>) =>
    api<Account>(`/accounts/${id}`, { method: 'PATCH', body }),
  )

export function useCreatePerson() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api<Person>('/people', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['people'] }),
  })
}

export function useUpdatePerson() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string } & Record<string, unknown>) =>
      api<Person>(`/people/${id}`, { method: 'PATCH', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['people'] }),
  })
}

export function useCreateCategory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api<Category>('/categories', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.categories }),
  })
}

// ---------- Cartões ----------
export function useCards(includeArchived = false) {
  return useQuery({
    queryKey: keys.cards(includeArchived),
    queryFn: ({ signal }) => api<CreditCard[]>(`/cards`, { query: { include_archived: includeArchived }, signal }),
  })
}

export function useCard(cardId: string) {
  return useQuery({
    queryKey: keys.card(cardId),
    queryFn: ({ signal }) => api<CreditCard>(`/cards/${cardId}`, { signal }),
    enabled: !!cardId,
  })
}

export function useCardStatements(cardId: string, status?: string) {
  return useQuery({
    queryKey: keys.cardStatements(cardId, status),
    queryFn: ({ signal }) => api<CardStatement[]>(`/cards/${cardId}/statements`, { query: { status }, signal }),
    enabled: !!cardId,
  })
}

export function useStatement(statementId: string) {
  return useQuery({
    queryKey: keys.statement(statementId),
    queryFn: ({ signal }) => api<CardStatement>(`/cards/statements/${statementId}`, { signal }),
    enabled: !!statementId,
  })
}

export function useStatementInstallments(statementId: string) {
  return useQuery({
    queryKey: keys.statementInstallments(statementId),
    queryFn: ({ signal }) => api<CardInstallment[]>(`/cards/statements/${statementId}/installments`, { signal }),
    enabled: !!statementId,
  })
}

export function useCardPurchases(cardId: string, filters: { from?: string; to?: string; status?: string } = {}) {
  return useQuery({
    queryKey: keys.cardPurchases(cardId, filters),
    queryFn: ({ signal }) => api<CardPurchase[]>(`/cards/${cardId}/purchases`, { query: filters, signal }),
    enabled: !!cardId,
    placeholderData: keepPreviousData,
  })
}

export function useUpcomingInstallments(cardId: string, limit = 20) {
  return useQuery({
    queryKey: keys.cardUpcoming(cardId, limit),
    queryFn: ({ signal }) => api<CardInstallment[]>(`/cards/${cardId}/upcoming`, { query: { limit }, signal }),
    enabled: !!cardId,
  })
}

// ---------- Contas da casa (Bills) ----------
export function useBills(includeArchived = false) {
  return useQuery({
    queryKey: keys.bills(includeArchived),
    queryFn: ({ signal }) => api<Bill[]>(`/bills`, { query: { include_archived: includeArchived }, signal }),
  })
}

export function useBill(billId: string) {
  return useQuery({
    queryKey: keys.bill(billId),
    queryFn: ({ signal }) => api<Bill>(`/bills/${billId}`, { signal }),
    enabled: !!billId,
  })
}

export function useRecurrences(billId?: string, status?: string) {
  return useQuery({
    queryKey: keys.recurrences(billId, status),
    queryFn: ({ signal }) =>
      api<Recurrence[]>(`/bills/recurrences`, { query: { bill_id: billId, status }, signal }),
  })
}

export function useRecurrence(recurrenceId: string) {
  return useQuery({
    queryKey: keys.recurrence(recurrenceId),
    queryFn: ({ signal }) => api<Recurrence>(`/bills/recurrences/${recurrenceId}`, { signal }),
    enabled: !!recurrenceId,
  })
}

export function useBillInstallments(filters: {
  bill_id?: string
  recurrence_id?: string
  status?: string
  due_from?: string
  due_to?: string
  page?: number
  limit?: number
}) {
  return useQuery({
    queryKey: keys.billInstallments(filters),
    queryFn: ({ signal }) => api<BillInstallmentPage>(`/bills/installments`, { query: filters, signal }),
    placeholderData: keepPreviousData,
  })
}

export function useBillInstallment(installmentId: string) {
  return useQuery({
    queryKey: keys.billInstallment(installmentId),
    queryFn: ({ signal }) => api<BillInstallment>(`/bills/installments/${installmentId}`, { signal }),
    enabled: !!installmentId,
  })
}

export function useUpcomingBillInstallments(days = 30) {
  return useQuery({
    queryKey: keys.upcomingInstallments(days),
    queryFn: ({ signal }) => api<BillInstallment[]>(`/bills/installments/upcoming`, { query: { days, limit: 20 }, signal }),
  })
}

export function useOverdueBillInstallments(limit = 50) {
  return useQuery({
    queryKey: keys.overdueInstallments(limit),
    queryFn: ({ signal }) => api<BillInstallment[]>(`/bills/installments/overdue`, { query: { limit }, signal }),
  })
}

export const useCreateCard = () =>
  useFinanceMutation((body: Record<string, unknown>) => api<CreditCard>('/cards', { method: 'POST', body }))

export const useUpdateCard = () =>
  useFinanceMutation(({ id, ...body }: { id: string } & Record<string, unknown>) =>
    api<CreditCard>(`/cards/${id}`, { method: 'PATCH', body }),
  )

export const useCreatePurchase = () =>
  useFinanceMutation((body: Record<string, unknown>) => api<CardPurchase>('/cards/purchases', { method: 'POST', body }))

export const usePayStatement = () =>
  useFinanceMutation(({ statementId, ...body }: { statementId: string } & Record<string, unknown>) =>
    api<StatementPayment>(`/cards/statements/${statementId}/payments`, { method: 'POST', body }),
  )

// ---------- Contas da casa (Bills) ----------
export const useCreateBill = () =>
  useFinanceMutation((body: Record<string, unknown>) => api<Bill>('/bills', { method: 'POST', body }))

export const useUpdateBill = () =>
  useFinanceMutation(({ id, ...body }: { id: string } & Record<string, unknown>) =>
    api<Bill>(`/bills/${id}`, { method: 'PATCH', body }),
  )

export const useArchiveBill = () =>
  useFinanceMutation((id: string) => api<Bill>(`/bills/${id}/archive`, { method: 'POST', body: {} }))

export const useRestoreBill = () =>
  useFinanceMutation((id: string) => api<Bill>(`/bills/${id}/restore`, { method: 'POST', body: {} }))

export const useCreateRecurrence = () =>
  useFinanceMutation((body: Record<string, unknown>) => api<Recurrence>('/bills/recurrences', { method: 'POST', body }))

export const useUpdateRecurrence = () =>
  useFinanceMutation(({ id, ...body }: { id: string } & Record<string, unknown>) =>
    api<Recurrence>(`/bills/recurrences/${id}`, { method: 'PATCH', body }),
  )

export const usePostRecurrenceInstallments = () =>
  useFinanceMutation(({ recurrenceId, ...body }: { recurrenceId: string } & Record<string, unknown>) =>
    api<BillInstallment[]>(`/bills/recurrences/${recurrenceId}/post-installments`, { method: 'POST', body }),
  )

export const useCreateBillInstallment = () =>
  useFinanceMutation((body: Record<string, unknown>) => api<BillInstallment>('/bills/installments', { method: 'POST', body }))

export const useUpdateBillInstallment = () =>
  useFinanceMutation(({ id, ...body }: { id: string } & Record<string, unknown>) =>
    api<BillInstallment>(`/bills/installments/${id}`, { method: 'PATCH', body }),
  )

export const usePayBillInstallment = () =>
  useFinanceMutation(
    // O endpoint recebe os dados de pagamento como query string.
    ({ installmentId, ...query }: {
      installmentId: string
      account_id: string
      paid_on: string
      amount_cents?: number
      idempotency_key?: string
    }) =>
      api<BillInstallment>(`/bills/installments/${installmentId}/pay`, { method: 'POST', query }),
  )

export const useReverseBillInstallment = () =>
  useFinanceMutation(
    ({ installmentId, ...body }: { installmentId: string } & Record<string, unknown>) =>
      api<BillInstallment>(`/bills/installments/${installmentId}/reverse`, { method: 'POST', body }),
  )

export const useSkipBillInstallment = () =>
  useFinanceMutation(
    ({ installmentId, ...body }: { installmentId: string } & Record<string, unknown>) =>
      api<BillInstallment>(`/bills/installments/${installmentId}/skip`, { method: 'POST', body }),
  )

export const useCancelBillInstallment = () =>
  useFinanceMutation(
    ({ installmentId, ...body }: { installmentId: string } & Record<string, unknown>) =>
      api<BillInstallment>(`/bills/installments/${installmentId}/cancel`, { method: 'POST', body }),
  )

export const useAutoPostBills = () =>
  useFinanceMutation((body: Record<string, unknown>) => api<BillInstallment[]>('/bills/auto-post', { method: 'POST', body }))

// ---------- Valores com terceiros ----------

export function usePartyBalances(filters: { person_id?: string; direction?: string; include_cancelled?: boolean } = {}) {
  return useQuery({
    queryKey: keys.parties(filters),
    queryFn: ({ signal }) => api<PartyBalancePage>('/party-balances', { query: filters, signal }),
    placeholderData: keepPreviousData,
  })
}

export function usePartyBalance(id: string | null) {
  return useQuery({
    queryKey: keys.party(id ?? ''),
    queryFn: ({ signal }) => api<PartyBalanceDetail>(`/party-balances/${id}`, { signal }),
    enabled: !!id,
  })
}

export function usePersonPosition(personId: string) {
  return useQuery({
    queryKey: keys.personPosition(personId),
    queryFn: ({ signal }) => api<PersonPosition>(`/people/${personId}/position`, { signal }),
  })
}

export const useCreatePartyBalance = () =>
  useFinanceMutation((body: Record<string, unknown>) =>
    api<PartyBalanceDetail>('/party-balances', { method: 'POST', body }),
  )

export const useSettlePartyBalance = () =>
  useFinanceMutation(({ id, ...body }: { id: string } & Record<string, unknown>) =>
    api<PartyBalanceDetail>(`/party-balances/${id}/settlements`, { method: 'POST', body }),
  )

export const useAdjustPartyBalance = () =>
  useFinanceMutation(({ id, ...body }: { id: string } & Record<string, unknown>) =>
    api<PartyBalanceDetail>(`/party-balances/${id}/adjustments`, { method: 'POST', body }),
  )

export const useReversePartySettlement = () =>
  useFinanceMutation(({ settlementId, reason }: { settlementId: string; reason: string }) =>
    api<PartyBalanceDetail>(`/party-balances/settlements/${settlementId}/reverse`, { method: 'POST', body: { reason } }),
  )

export const useCancelPartyBalance = () =>
  useFinanceMutation(({ id, reason }: { id: string; reason: string }) =>
    api<PartyBalanceDetail>(`/party-balances/${id}/cancel`, { method: 'POST', body: { reason } }),
  )
