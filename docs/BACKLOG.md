# Backlog priorizado

## Etapa 1 — Fundação (em andamento)
- [x] Docs de arquitetura, regras e decisões
- [ ] Supabase local com signup desligado
- [ ] Backend: config, acesso do proprietário, erros padronizados, sessão de banco
- [ ] Migration inicial: settings, contas, categorias (seed), pessoas, transações, auditoria; RLS
- [ ] API: contas, extrato, lançamentos, transferências, pessoas, categorias, dashboard inicial
- [ ] Testes: acesso negado, identidade errada, idempotência, transferência preserva soma, saldo
- [ ] Frontend: login, layout com sidebar, transições, Dashboard, Contas, Lançamentos, Pessoas
- [ ] CI básica

## Etapa 2 — Cartões e faturas
Cadastro de cartão, `resolve_statement_for_purchase`, ciclos materializados, compras/parcelas, pagamento de fatura, utilização de limite.

## Etapa 3 — Contas da casa e recorrências
Obrigações, recorrências idempotentes, estimado × real, calendário, alertas in-app, rateios.

## Etapa 4 — Valores com terceiros
Empréstimos, adiantamentos, acertos parciais, tela por pessoa.

## Etapa 5 — Inteligência e acabamento
Orçamentos, metas, projeção 30/60/90, relatórios, exportações, backup/restore.
