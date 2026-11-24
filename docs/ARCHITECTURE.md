# Arquitetura — Finance Hub Pessoal

Aplicação **single-user**. Um proprietário, um banco lógico, sem multi-tenancy.

## Visão geral

```
Navegador (React + Vite)
   │  1. login e-mail/senha  ──────────────▶  Supabase Auth (signup DESLIGADO)
   │  2. Authorization: Bearer <JWT>
   ▼
FastAPI  /api/v1
   ├─ owner_access: valida assinatura do JWT (JWKS / segredo) + `sub == OWNER_SUBJECT`
   ├─ api/v1/*        → transporte HTTP, validação Pydantic
   ├─ domains/*       → regras puras e serviços de domínio (fonte de verdade)
   └─ SQLAlchemy      → transação PostgreSQL (Supabase) + audit_events
```

- O navegador **só** usa a `anon key` do Supabase para autenticar. Nenhuma tabela financeira é exposta via PostgREST:
  todas têm RLS habilitado e **nenhuma policy**, e os privilégios de `anon`/`authenticated` são revogados no schema `public`.
- O FastAPI conecta direto ao Postgres (role `postgres` no dev; role dedicada com privilégio mínimo em produção).
- Migrations: **Alembic** é a única fonte do schema (a pasta `supabase/` só configura Auth e serviços locais).

## Camadas do backend

| Camada | Pasta | Responsabilidade |
|---|---|---|
| Core | `app/core` | config, segurança (JWT), acesso do proprietário, sessão de banco, erros padronizados, logging |
| Modelos | `app/models` | tabelas SQLAlchemy |
| Schemas | `app/schemas` | contratos da API (centavos inteiros `*_cents`) |
| Domínio | `app/domains` | regras puras (dinheiro, saldo, idempotência) e serviços transacionais |
| API | `app/api/v1` | rotas finas que chamam serviços |

## Agregados (Etapa 1)

- **FinancialAccount** — conta/carteira; saldo = saldo inicial + Σ transações `POSTED`.
- **Transaction** — livro de caixa. Toda alteração de saldo passa por aqui, gerada por serviço de domínio.
- **Transfer** — par de transações com o mesmo `transfer_group_id` (origem negativa, destino positiva).
- **Category**, **Person** (contato sem login), **AppSettings** (singleton), **AuditEvent**.

Etapas seguintes adicionam: cartões/faturas/parcelas (2), obrigações/recorrências/rateios (3), saldos com terceiros (4), orçamentos/metas/projeções (5).

## Frontend

React + TypeScript + Vite, Tailwind + componentes no padrão shadcn/ui, TanStack Query, React Hook Form + Zod, Recharts, `motion` (transições de rota com `AnimatePresence`, `MotionConfig reducedMotion="user"`).
O frontend **não calcula** saldos: exibe o que a API devolve. Formatação BRL e parse de entrada para centavos ficam em `lib/money`.

Design system: `design-system/finance-hub/MASTER.md` (gerado com a skill ui-ux-pro-max), com a paleta ajustada em `docs/DECISIONS.md`.

## Execução local

Ver `README.md`.
