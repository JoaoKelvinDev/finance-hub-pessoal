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
```

## Segurança

- Não existe cadastro de usuários: `enable_signup = false` no Supabase e a API aceita **apenas** o `OWNER_SUBJECT`.
- O navegador recebe só a `anon key` (pública). `SUPABASE_SERVICE_ROLE_KEY` e `DATABASE_URL` ficam no servidor.
- Nunca commite o `.env`.

## Estado atual

Etapas 0 a 4 concluídas: contas e lançamentos, cartões e faturas, contas da casa com recorrências (estimado × real, rateios e alertas in-app), valores com terceiros e calendário financeiro. A Etapa 5 (orçamentos, metas, projeção, relatórios e exportações) está em [`docs/BACKLOG.md`](docs/BACKLOG.md).
