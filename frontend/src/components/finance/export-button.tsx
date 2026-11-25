import { Download } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { ApiError, apiDownload } from '@/lib/api'
import { addDays, todayISO } from '@/lib/date'

export type ExportKind =
  | 'transactions'
  | 'card-purchases'
  | 'party-balances'
  | 'categories'
  | 'cash-flow'
  | 'cards'
  | 'counterparties'

/** Baixa o CSV (Excel pt-BR) do período. Sem período ("Tudo"), usa os últimos 2 anos. */
export function ExportButton({
  kind,
  from,
  to,
  basis,
  label = 'Exportar CSV',
}: {
  kind: ExportKind
  from?: string
  to?: string
  basis?: string
  label?: string
}) {
  const [busy, setBusy] = useState(false)
  const end = to || todayISO()
  // 730 dias cabem no limite da API (2 anos) e evitam datas inválidas como 29/02.
  const start = from || addDays(end, -730)
  return (
    <Button
      variant="secondary"
      loading={busy}
      onClick={async () => {
        setBusy(true)
        try {
          const name = await apiDownload(`/exports/${kind}.csv`, { from: start, to: end, basis })
          toast.success(`Arquivo ${name} baixado.`)
        } catch (err) {
          toast.error(err instanceof ApiError ? err.message : 'Não foi possível exportar.')
        } finally {
          setBusy(false)
        }
      }}
    >
      <Download /> {label}
    </Button>
  )
}
