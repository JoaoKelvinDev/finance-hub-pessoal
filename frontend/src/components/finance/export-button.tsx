import { ChevronDown, Download, FileSpreadsheet, FileText, Table2 } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { downloadExport, exportRange } from '@/lib/exports'
import { cn } from '@/lib/utils'

export type ExportKind =
  | 'transactions'
  | 'card-purchases'
  | 'party-balances'
  | 'categories'
  | 'cash-flow'
  | 'cards'
  | 'counterparties'

export type ExportFormat = 'csv' | 'xlsx' | 'pdf'

const FORMATS: { value: ExportFormat; label: string; hint: string; icon: typeof FileText }[] = [
  { value: 'xlsx', label: 'Excel (XLSX)', hint: 'Valores e datas prontos para somar e filtrar', icon: FileSpreadsheet },
  { value: 'pdf', label: 'PDF', hint: 'Para guardar ou imprimir', icon: FileText },
  { value: 'csv', label: 'CSV', hint: 'Texto simples (Excel pt-BR)', icon: Table2 },
]

/** Menu de exportação: XLSX, PDF ou CSV do período. */
export function ExportButton({
  kind,
  from,
  to,
  basis,
  label = 'Exportar',
}: {
  kind: ExportKind
  from?: string
  to?: string
  basis?: string
  label?: string
}) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState<ExportFormat | null>(null)
  const root = useRef<HTMLDivElement>(null)
  const items = useRef<(HTMLButtonElement | null)[]>([])
  const menuId = useId()

  useEffect(() => {
    if (!open) return
    items.current[0]?.focus()
    const onDown = (e: PointerEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', onDown)
    return () => document.removeEventListener('pointerdown', onDown)
  }, [open])

  const run = async (fmt: ExportFormat) => {
    setOpen(false)
    setBusy(fmt)
    await downloadExport(`/exports/${kind}.${fmt}`, { ...exportRange(from, to), basis })
    setBusy(null)
  }

  return (
    <div
      ref={root}
      className="relative"
      onKeyDown={(e) => {
        if (!open) return
        const idx = items.current.findIndex((el) => el === document.activeElement)
        if (e.key === 'Escape') {
          e.preventDefault()
          setOpen(false)
          root.current?.querySelector<HTMLButtonElement>('[aria-haspopup]')?.focus()
        } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
          e.preventDefault()
          const n = FORMATS.length
          items.current[(idx + (e.key === 'ArrowDown' ? 1 : n - 1) + n) % n]?.focus()
        }
      }}
    >
      <Button
        variant="secondary"
        loading={busy !== null}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((v) => !v)}
      >
        <Download /> {busy ? `Gerando ${busy.toUpperCase()}…` : label}
        <ChevronDown className={cn('transition-transform', open && 'rotate-180')} />
      </Button>
      {open && (
        <div
          id={menuId}
          role="menu"
          aria-label="Formato do arquivo"
          className="absolute right-0 z-30 mt-1.5 w-72 overflow-hidden rounded-xl border border-border bg-surface p-1 shadow-lg"
        >
          {FORMATS.map((f, i) => (
            <button
              key={f.value}
              ref={(el) => {
                items.current[i] = el
              }}
              type="button"
              role="menuitem"
              onClick={() => run(f.value)}
              className="flex w-full items-start gap-3 rounded-lg px-3 py-2 text-left outline-none transition-colors hover:bg-surface-2 focus-visible:bg-surface-2"
            >
              <f.icon className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
              <span>
                <span className="block text-sm font-medium">{f.label}</span>
                <span className="block text-xs text-muted">{f.hint}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
