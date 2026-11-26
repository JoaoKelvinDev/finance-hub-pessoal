# Finance Hub Pessoal

Painel financeiro **privado e de uso individual** (single-user). Especificação completa em [`FINANCE_HUB_PESSOAL.md`](FINANCE_HUB_PESSOAL.md); decisões em [`docs/`](docs/).

- **Backend:** FastAPI + SQLAlchemy + Alembic, regras financeiras em centavos.
- **Banco e login:** Supabase (Postgres + Auth com cadastro público desligado). Dados financeiros só passam pela API; RLS ligado sem policies.
- **Frontend:** React + Vite + Tailwind + componentes estilo shadcn, TanStack Query, Recharts e `motion` para transições.

## Rodando localmente

Pré-requisitos: Docker Desktop, Supabase CLI, Node 22+, Python 3.12+ com [uv](https://docs.astral.sh/uv/).

```bash
# 1. Supabase local (Postgres + Auth)
supabase start -x edge-runtime,logflare,vector,imgproxy,storage-api,realtime,supavisor
supabase status            # mostra JWT_SECRET, ANON_KEY e SERVICE_ROLE_KEY

# 2. Configuração
cp .env.example .env       # preencha com os valores do `supabase status`

# 3. Backend
cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.cli create-owner --email voce@exemplo.com   # cria o ÚNICO usuário
#   -> copie o OWNER_SUBJECT impresso para o .env
uv run uvicorn app.main:app --reload --port 8000

# 4. Frontend (outro terminal)
cd frontend
npm install
npm run dev                # http://localhost:5173
```

## Testes

```bash
cd backend && uv run pytest        # usa um banco isolado `finance_hub_test` no Postgres local
cd frontend && npm run build       # checagem de tipos + build
cd frontend && npm run e2e         # fluxos reais no navegador (Playwright), banco isolado `finance_hub_e2e`
cd frontend && npm run e2e:ui      # o mesmo, assistindo os testes rodarem
cd frontend && npm run e2e:report  # relatório da última execução (capturas e trace das falhas)
```

Os testes E2E sobem sozinhos uma API (porta 8010) e um frontend (porta 5180) próprios, com segredo JWT e
proprietário de teste, e zeram o banco `finance_hub_e2e` antes de cada teste — seus dados nunca são tocados.
Precisam do Postgres local (`supabase start`) e, localmente, usam o Microsoft Edge instalado. Cobrem: acesso,
conta e lançamentos, transferência, cartão (compra parcelada → faturas → pagamento sem dupla contagem), contas
da casa + calendário, terceiros, orçamento, relatórios com download (XLSX/PDF/CSV) e uso no celular, além de
verificação de acessibilidade (axe, WCAG 2.1 AA) nas telas principais. Rodam no CI em todo PR.

## Produção (gratuito)

- **App**: https://finance-hub-pessoal.vercel.app — Vercel Hobby com **Services** (beta): frontend Vite e
  API FastAPI no mesmo projeto e domínio (`vercel.json`). Publica sozinho a cada push na `main`.
- **Banco + login**: Supabase Free, projeto `finance-hub` (São Paulo). Cadastro público desligado; só o
  `OWNER_SUBJECT` acessa. A API usa o pooler em modo transação (porta 6543).
- **Migrações**: workflow `Migrações (produção)` roda `alembic upgrade head` quando a `main` muda
  (secret `PROD_MIGRATIONS_DATABASE_URL`, pooler em modo sessão, porta 5432).
- **Backup**: repositório **privado** `finance-hub-backups` — `pg_dump` diário criptografado (AES-256),
  guardado 90 dias e **restaurado num banco vazio a cada execução** para provar que funciona. O acesso
  diário também evita que o Supabase gratuito pause o projeto. A senha fica no gerenciador de senhas do dono.
- Variáveis na Vercel: `DATABASE_URL`, `SUPABASE_URL`, `OWNER_SUBJECT`, `CORS_ORIGINS`, `APP_TIMEZONE`,
  `DOCS_ENABLED=false`, `LOG_LEVEL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` (chave *publishable*).

## Segurança

- Não existe cadastro de usuários: `enable_signup = false` no Supabase e a API aceita **apenas** o `OWNER_SUBJECT`.
- O navegador recebe só a `anon key` (pública). `SUPABASE_SERVICE_ROLE_KEY` e `DATABASE_URL` ficam no servidor.
- Nunca commite o `.env`.

## Estado atual

Etapas 0 a 4 concluídas: contas e lançamentos, cartões e faturas, contas da casa com recorrências (estimado × real, rateios e alertas in-app), valores com terceiros e calendário financeiro. A Etapa 5 (orçamentos, metas, projeção, relatórios e exportações) está em [`docs/BACKLOG.md`](docs/BACKLOG.md).
