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

## Etapa 4 — Valores com terceiros
Empréstimos, adiantamentos, acertos parciais, tela por pessoa.

## Etapa 5 — Inteligência e acabamento
Orçamentos, metas, projeção 30/60/90, relatórios, exportações, backup/restore.
