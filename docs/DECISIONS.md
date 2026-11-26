# Decisões (ADR resumido)

| # | Decisão | Motivo |
|---|---|---|
| 1 | **Supabase** no lugar de PostgreSQL próprio (Postgres + Auth) | Pedido do proprietário; Auth gerenciado evita autenticação caseira |
| 2 | Regras financeiras no **FastAPI**; o navegador nunca lê tabelas via PostgREST | Spec §14.1; backend é a fonte de verdade e é testável em Python |
| 3 | RLS **habilitado sem policies** e `REVOKE` para `anon`/`authenticated` em `public` | Defesa em profundidade caso a anon key vaze |
| 4 | `enable_signup = false` + checagem `sub == OWNER_SUBJECT` no backend | Uma única identidade; sem cadastro público |
| 5 | Dev com `supabase start` (Docker) em vez de Docker Compose próprio | O CLI já sobe Postgres + Auth + Studio |
| 6 | **Alembic** é o dono do schema | Uma única ferramenta de migração, ligada aos modelos SQLAlchemy |
| 7 | Contrato monetário: **centavos inteiros** (`*_cents`) | Sem ambiguidade de formato decimal |
| 8 | Paleta: grafite/off-white + **um destaque azul**; verde/vermelho só para entrada/saída com sinal e rótulo | Spec §16; a sugestão dourado+roxo da skill foi descartada por conflitar com "um destaque" e com cores de alerta |
| 9 | Fonte **IBM Plex Sans** com `tabular-nums` | Recomendação da skill ui-ux-pro-max para finanças |
| 10 | Animações com `motion`: transição de rota de 180–220 ms, stagger leve, sem overshoot em dados; `reducedMotion="user"` | Fluidez sem prejudicar leitura de números |
| 11 | Timezone padrão `America/Fortaleza`; datas civis como `DATE` | Spec §1 |
| 12 | Sem modo "sem login": testes assinam JWTs com um segredo de teste | Spec §2.3 — nunca dispensar login por padrão |
| 13 | JWT verificado por **JWKS** (chaves assimétricas do Supabase) ou, se configurado, segredo HS256 legado | Compatível com Supabase local e nuvem |
| 14 | XLSX com **openpyxl** e PDF com **reportlab** (fontes padrão, sem HTML→PDF) | Python puro: nada de GTK/navegador no Windows ou no CI; WeasyPrint exigiria bibliotecas nativas |

## Pendências não bloqueantes (defaults adotados)

- Compra no dia do fechamento: intervalo `[início, fechamento)` (Etapa 2).
- Dia inexistente no mês: último dia do mês.
- Apenas BRL nos totais consolidados.
