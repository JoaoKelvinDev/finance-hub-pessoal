import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardContent } from '@/components/ui/card'
import { BillList } from '@/features/bills/BillList'
import { RecurrenceList } from '@/features/bills/RecurrenceList'
import { InstallmentList } from '@/features/bills/InstallmentList'
import { NewBillDialog } from '@/features/bills/NewBillDialog'
import { NewRecurrenceDialog } from '@/features/bills/NewRecurrenceDialog'
import { NewInstallmentDialog } from '@/features/bills/NewInstallmentDialog'
import { PayInstallmentDialog } from '@/features/bills/PayInstallmentDialog'
import type { Recurrence } from '@/types/api'
import type { BillInstallment } from '@/types/api'

export function BillsPage() {
  const [activeTab, setActiveTab] = useState<'bills' | 'recurrences' | 'installments'>('bills')
  const [newBillOpen, setNewBillOpen] = useState(false)
  const [newRecurrenceOpen, setNewRecurrenceOpen] = useState(false)
  const [newInstallmentOpen, setNewInstallmentOpen] = useState(false)
  const [selectedBill, setSelectedBill] = useState<{ id: string; name: string } | null>(null)
  const [selectedRecurrence, setSelectedRecurrence] = useState<{ id: string; name: string } | null>(null)
  const [payInstallment, setPayInstallment] = useState<{ id: string; billName: string } | null>(null)

  const handleNewBill = () => {
    setNewBillOpen(true)
  }

  const handleNewRecurrence = () => {
    if (!selectedBill) return
    setNewRecurrenceOpen(true)
  }

  const handleNewInstallment = (recurrence?: { id: string; name: string }) => {
    if (!selectedBill) return
    setSelectedRecurrence(recurrence || null)
    setNewInstallmentOpen(true)
  }

  const handleBillClick = (bill: { id: string; name: string }) => {
    setSelectedBill(bill)
    setActiveTab('recurrences')
  }

  const handleRecurrenceClick = (recurrence: Recurrence) => {
    setSelectedRecurrence({ id: recurrence.id, name: recurrence.bill_name || 'Recorrência' })
    setActiveTab('installments')
  }

  const handleInstallmentClick = (installment: BillInstallment) => {
    setPayInstallment({ id: installment.id, billName: installment.bill_name || 'Parcela' })
  }

  return (
    <div className="mx-auto max-w-[1400px] space-y-5">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Contas da casa</h1>
          <p className="text-muted mt-0.5">Gerencie contas recorrentes (aluguel, água, internet, etc.), suas recorrências e parcelas.</p>
        </div>
        <Button onClick={handleNewBill} disabled={activeTab !== 'bills'}>
          <Plus className="size-4 mr-2" /> Nova conta
        </Button>
      </div>

      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'bills' | 'recurrences' | 'installments')} className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="bills">Contas</TabsTrigger>
          <TabsTrigger value="recurrences" disabled={!selectedBill}>Recorrências</TabsTrigger>
          <TabsTrigger value="installments" disabled={!selectedRecurrence}>Parcelas</TabsTrigger>
        </TabsList>

        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0, transition: { duration: 0.2 } }}
            exit={{ opacity: 0, x: -20, transition: { duration: 0.15 } }}
            className="mt-4"
          >
            {activeTab === 'bills' && (
              <Card>
                <CardHeader
                  title="Contas da casa"
                  action={
                    <Button onClick={handleNewBill} size="sm">
                      <Plus className="size-4 mr-1" /> Nova
                    </Button>
                  }
                />
                <CardContent>
                  <BillList onBillClick={handleBillClick} />
                </CardContent>
              </Card>
            )}

            {activeTab === 'recurrences' && selectedBill && (
              <Card>
                <CardHeader
                  title={`Recorrências de ${selectedBill.name}`}
                  action={
                    <>
                      <Button variant="secondary" size="sm" onClick={() => setActiveTab('bills')}>
                        Voltar
                      </Button>
                      <Button onClick={handleNewRecurrence} size="sm">
                        <Plus className="size-4 mr-1" /> Nova recorrência
                      </Button>
                    </>
                  }
                />
                <CardContent>
                  <RecurrenceList billId={selectedBill.id} onRecurrenceClick={handleRecurrenceClick} />
                </CardContent>
              </Card>
            )}

            {activeTab === 'installments' && selectedRecurrence && (
              <Card>
                <CardHeader
                  title={`Parcelas de ${selectedRecurrence.name}`}
                  action={
                    <>
                      <Button variant="secondary" size="sm" onClick={() => setActiveTab('recurrences')}>
                        Voltar
                      </Button>
                      <Button onClick={() => handleNewInstallment(selectedRecurrence)} size="sm">
                        <Plus className="size-4 mr-1" /> Nova parcela
                      </Button>
                    </>
                  }
                />
                <CardContent>
                  <InstallmentList recurrenceId={selectedRecurrence.id} onInstallmentClick={handleInstallmentClick} />
                </CardContent>
              </Card>
            )}

            {activeTab === 'installments' && selectedBill && !selectedRecurrence && (
              <Card>
                <CardHeader
                  title={`Todas as parcelas de ${selectedBill.name}`}
                  action={
                    <>
                      <Button variant="secondary" size="sm" onClick={() => setActiveTab('recurrences')}>
                        Voltar
                      </Button>
                      <Button onClick={() => handleNewInstallment()} size="sm">
                        <Plus className="size-4 mr-1" /> Nova parcela
                      </Button>
                    </>
                  }
                />
                <CardContent>
                  <InstallmentList billId={selectedBill.id} onInstallmentClick={handleInstallmentClick} />
                </CardContent>
              </Card>
            )}
          </motion.div>
        </AnimatePresence>
      </Tabs>

      {/* Dialogs */}
      <NewBillDialog open={newBillOpen} onOpenChange={setNewBillOpen} onSuccess={() => setNewBillOpen(false)} />
      <NewRecurrenceDialog
        open={newRecurrenceOpen}
        onOpenChange={setNewRecurrenceOpen}
        billId={selectedBill?.id || ''}
        billName={selectedBill?.name || ''}
        onSuccess={() => setNewRecurrenceOpen(false)}
      />
      <NewInstallmentDialog
        open={newInstallmentOpen}
        onOpenChange={setNewInstallmentOpen}
        bill={selectedBill ? { id: selectedBill.id, name: selectedBill.name, default_amount_cents: 0, color: '#EF4444' } as any : null}
        recurrence={selectedRecurrence ? { id: selectedRecurrence.id, name: selectedRecurrence.name } as any : null}
        onSuccess={() => setNewInstallmentOpen(false)}
      />
      <PayInstallmentDialog
        open={!!payInstallment}
        onOpenChange={(open) => { if (!open) setPayInstallment(null); }}
        installment={payInstallment ? { id: payInstallment.id, bill_name: payInstallment.billName, due_date: '', amount_cents: 0 } as any : null}
        onSuccess={() => setPayInstallment(null)}
      />
    </div>
  )
}