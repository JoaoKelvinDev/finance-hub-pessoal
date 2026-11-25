import { AnimatePresence, motion } from 'motion/react'
import { Archive, ArchiveRestore, Plus, Users } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { EmptyState, ErrorState } from '@/components/finance/states'
import { ListSkeleton } from '@/components/finance/transaction-list'
import { Button } from '@/components/ui/button'
import { Card, CardHeader } from '@/components/ui/card'
import { Dialog } from '@/components/ui/dialog'
import { Field, Input, Textarea } from '@/components/ui/field'
import { ApiError } from '@/lib/api'
import { listItem } from '@/lib/motion'
import { useCreatePerson, usePeople, useUpdatePerson } from '@/lib/queries'

export function PeoplePage() {
  const { data, isLoading, isError, refetch } = usePeople(true)
  const update = useUpdatePerson()
  const [open, setOpen] = useState(false)

  return (
    <div className="mx-auto max-w-[900px] space-y-4">
      <Card className="overflow-hidden">
        <CardHeader
          title="Contatos financeiros"
          description="Pessoas com quem você divide despesas ou tem valores a receber/pagar. Elas não têm acesso ao sistema."
          action={
            <Button size="sm" onClick={() => setOpen(true)}>
              <Plus /> Nova pessoa
            </Button>
          }
        />
        {isError ? (
          <ErrorState onRetry={() => refetch()} />
        ) : isLoading || !data ? (
          <ListSkeleton rows={3} />
        ) : data.length === 0 ? (
          <EmptyState
            icon={<Users />}
            title="Nenhum contato"
            description="Cadastre familiares ou conhecidos para registrar empréstimos, adiantamentos e dívidas."
          />
        ) : (
          <ul className="divide-y divide-border">
            <AnimatePresence initial={false}>
              {data.map((p) => (
                <motion.li
                  key={p.id}
                  layout="position"
                  variants={listItem}
                  initial="initial"
                  animate="enter"
                  exit="exit"
                  className={`flex items-center gap-3 px-5 py-3 ${p.archived_at ? 'opacity-55' : ''}`}
                >
                  <span className="grid size-9 place-items-center rounded-full bg-accent-soft text-sm font-semibold text-accent" aria-hidden>
                    {p.display_name.slice(0, 1).toUpperCase()}
                  </span>
                  <div className="min-w-0 flex-1">
                    <Link to={`/pessoas/${p.id}`} className="block truncate text-sm font-medium hover:underline">
                      {p.display_name}
                    </Link>
                    <p className="truncate text-xs text-muted">{[p.contact, p.notes].filter(Boolean).join(' · ') || 'Sem detalhes'}</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={async () => {
                      try {
                        await update.mutateAsync({ id: p.id, archived: !p.archived_at })
                      } catch (e) {
                        toast.error(e instanceof ApiError ? e.message : 'Falha ao atualizar.')
                      }
                    }}
                  >
                    {p.archived_at ? <ArchiveRestore /> : <Archive />}
                    <span className="hidden sm:inline">{p.archived_at ? 'Reativar' : 'Arquivar'}</span>
                  </Button>
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        )}
      </Card>
      <PersonDialog open={open} onOpenChange={setOpen} />
    </div>
  )
}

function PersonDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const create = useCreatePerson()
  const [name, setName] = useState('')
  const [contact, setContact] = useState('')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState<string>()

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title="Nova pessoa" description="Apenas um registro para seus controles; não cria login.">
      <form
        className="flex flex-col gap-4"
        onSubmit={async (e) => {
          e.preventDefault()
          if (!name.trim()) return setError('Informe o nome.')
          try {
            await create.mutateAsync({ display_name: name, contact: contact || null, notes: notes || null })
            toast.success(`${name} adicionado(a).`)
            setName('')
            setContact('')
            setNotes('')
            setError(undefined)
            onOpenChange(false)
          } catch (err) {
            toast.error(err instanceof ApiError ? err.message : 'Não foi possível salvar.')
          }
        }}
      >
        <Field label="Nome" error={error}>
          {(p) => <Input {...p} autoFocus value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />}
        </Field>
        <Field label="Contato (opcional)" hint="Telefone ou e-mail, só para referência.">
          {(p) => <Input {...p} value={contact} onChange={(e) => setContact(e.target.value)} maxLength={120} />}
        </Field>
        <Field label="Observações">{(p) => <Textarea {...p} value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button type="submit" loading={create.isPending}>
            Salvar
          </Button>
        </div>
      </form>
    </Dialog>
  )
}
