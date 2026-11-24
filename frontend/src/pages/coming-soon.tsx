import { Construction } from 'lucide-react'
import { useParams } from 'react-router-dom'
import { EmptyState } from '@/components/finance/states'
import { Card } from '@/components/ui/card'

const MODULES: Record<string, { title: string; stage: number; text: string }> = {
  cartoes: { title: 'Cartões e faturas', stage: 2, text: 'Ciclos de fatura, compras parceladas, limite e pagamento de fatura sem dupla contagem.' },
  'contas-da-casa': { title: 'Contas da casa', stage: 3, text: 'Mensalidades, recorrências, contas variáveis estimadas e rateios.' },
  calendario: { title: 'Calendário financeiro', stage: 3, text: 'Vencimentos de faturas, contas e recebimentos em visão mensal e semanal.' },
  terceiros: { title: 'Valores com terceiros', stage: 4, text: 'Empréstimos, adiantamentos, reembolsos e acertos parciais por pessoa.' },
  planejamento: { title: 'Planejamento', stage: 5, text: 'Orçamentos por categoria, metas e projeção de 30/60/90 dias.' },
  relatorios: { title: 'Relatórios', stage: 5, text: 'Relatórios por categoria, período e pessoa, com exportação CSV.' },
}

export function ComingSoonPage() {
  const { mod = '' } = useParams()
  const m = MODULES[mod] ?? { title: 'Módulo', stage: 0, text: 'Em planejamento.' }
  return (
    <Card className="mx-auto max-w-xl">
      <EmptyState
        icon={<Construction />}
        title={`${m.title} — Etapa ${m.stage}`}
        description={`${m.text} Este módulo será desenvolvido após a aprovação da etapa correspondente.`}
      />
    </Card>
  )
}
