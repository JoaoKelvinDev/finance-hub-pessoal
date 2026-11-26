import { toast } from 'sonner'
import { ApiError, apiDownload } from '@/lib/api'
import { addDays, todayISO } from '@/lib/date'

/** Período efetivo da exportação. Sem período ("Tudo"), usa os últimos 2 anos (limite da API). */
export function exportRange(from?: string, to?: string) {
  const end = to || todayISO()
  // 730 dias cabem no limite da API (2 anos) e evitam datas inválidas como 29/02.
  return { from: from || addDays(end, -730), to: end }
}

/** Baixa um arquivo da API e avisa o resultado. */
export async function downloadExport(path: string, params: Record<string, string | undefined>) {
  try {
    const name = await apiDownload(path, params)
    toast.success(`Arquivo ${name} baixado.`)
  } catch (err) {
    toast.error(err instanceof ApiError ? err.message : 'Não foi possível exportar.')
  }
}
