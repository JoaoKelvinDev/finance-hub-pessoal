import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Account, Category, Dashboard, Ledger, Person, Transaction, TransactionPage } from '@/types/api'

export const keys = {
  dashboard: (from: string, to: string) => ['dashboard', from, to] as const,
  accounts: (archived: boolean) => ['accounts', archived] as const,
  ledger: (id: string, page: number) => ['ledger', id, page] as const,
  transactions: (q: object) => ['transactions', q] as const,
  categories: ['categories'] as const,
  people: (archived: boolean) => ['people', archived] as const,
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
      for (const k of ['dashboard', 'accounts', 'ledger', 'transactions']) {
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
