# Backlog priorizado

## Etapa 1 — Fundação (concluída)
- [x] Docs de arquitetura, regras e decisões
- [x] Supabase local com signup desligado
- [x] Backend: config, acesso do proprietário, erros padronizados, sessão de banco
- [x] Migration inicial: settings, contas, categorias (seed), pessoas, transações, auditoria; RLS
- [x] API: contas, extrato, lançamentos, transferências, pessoas, categorias, dashboard inicial
- [x] Testes: acesso negado, identidade errada, idempotência, transferência preserva soma, saldo
- [x] Frontend: login, layout com sidebar, transições, Dashboard, Contas, Lançamentos, Pessoas
- [x] CI básica

Pendências conhecidas: rate limit próprio na API (hoje só o do Supabase Auth), exportação CSV (Etapa 5), testes E2E automatizados no repositório (validado manualmente com Playwright).

## Etapa 2 — Cartões e faturas
Cadastro de cartão, `resolve_statement_for_purchase`, ciclos materializados, compras/parcelas, pagamento de fatura, utilização de limite.

## Etapa 3 — Contas da casa e recorrências
Obrigações, recorrências idempotentes, estimado × real, calendário, alertas in-app, rateios.

- [x] Contas, recorrências e parcelas (pagar/estornar/pular/cancelar, idempotência, auditoria)
- [x] Calendário financeiro: `GET /calendar?from=&to=` (máx. 92 dias) unificando faturas, parcelas de contas,
      previsões virtuais de recorrências (descartadas quando já há parcela com mesmo `recurrence_id`+`due_date`)
      e lançamentos `PLANNED`; pagamentos não viram eventos próprios. Página `/calendario` com Mês, Semana e Agenda.
- [ ] Estimado × real em contas variáveis, alertas in-app, rateios com contatos

## Etapa 4 — Valores com terceiros
Empréstimos, adiantamentos, acertos parciais, tela por pessoa.

- [x] `party_balances` / `party_settlements` / `party_adjustments` (migração 0004) e kinds
      `LOAN_OUT`, `LOAN_IN`, `SETTLEMENT_IN`, `SETTLEMENT_OUT` — nunca contam como receita/despesa
- [x] Tipos: emprestei, paguei por alguém, peguei emprestado, alguém me deve, eu devo
- [x] Acertos parciais idempotentes, estorno, juros/desconto (perdão), cancelamento sem acertos ativos
- [x] Saldo em aberto derivado; status OPEN/PARTIALLY_SETTLED/SETTLED/OVERDUE/CANCELLED; sem compensação automática
- [x] Lançamentos gerados só podem ser desfeitos pelo módulo (`managed_by_parties`)
- [x] Calendário (`PARTY_BALANCE`), KPIs `receivables`/`payables` no dashboard
- [x] Telas `/terceiros` e `/pessoas/:id`
- [ ] Parcelamento combinado de empréstimo, comprovantes, juros recebidos como receita financeira separada

## Etapa 5 — Inteligência e acabamento
Orçamentos, metas, projeção 30/60/90, relatórios, exportações, backup/restore.
