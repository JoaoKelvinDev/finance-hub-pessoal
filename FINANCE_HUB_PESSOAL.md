# FINANCE HUB PESSOAL — Especificação funcional e técnica (Single User)

> **Documento de referência para implementação com Claude Code / Codex.**
> Produto: aplicação web privada de gestão financeira **estritamente individual (single-user)**, acessada exclusivamente pelo proprietário.
> Idioma padrão: português brasileiro (pt-BR). Moeda padrão: BRL (R$). Fuso horário configurável, padrão `America/Fortaleza`.
> Escopo obrigatório: **um proprietário, um espaço financeiro, sem cadastro público, sem equipe, sem compartilhamento de acesso e sem multi-tenancy**.
> Estado inicial: planejamento e arquitetura. **Não iniciar implementação antes de inspecionar o repositório e apresentar um plano.**

---

## 1. Visão do produto

Desenvolver um sistema de **controle financeiro pessoal e da casa**, com foco em:

- Cartões de crédito, limites, faturas, fechamento, vencimentos, compras parceladas e pagamentos.
- Contas, boletos, mensalidades, assinaturas e despesas recorrentes da residência.
- Receitas, despesas, transferências entre contas, saldos e fluxo de caixa.
- Valores emprestados, adiantados ou pagos em nome de terceiros; valores a receber e a devolver; liquidações parciais.
- Registro **individual** de despesas compartilhadas e reembolsos por familiares ou conhecidos, sem dar acesso dessas pessoas ao sistema.
- Dashboard detalhado, visão mensal e anual, alertas acionáveis, calendário financeiro e relatórios.

**Objetivo:** responder com precisão e rapidamente: **quanto tenho, quanto devo, quanto me devem, o que vence, quanto do orçamento já comprometi e como estarão meus próximos meses?**

### 1.1 Princípios inegociáveis

1. **Valores monetários nunca usam ponto flutuante**: armazenar em centavos como inteiro (`BIGINT`) ou `NUMERIC(18,2)` no PostgreSQL; API usa strings decimais ou centavos inteiros; cálculos consistentes.
2. **Sem dupla contagem**: compra no cartão não debita saldo bancário; pagamento da fatura debita conta bancária, mas não duplica a despesa por categoria nos relatórios de consumo.
3. **Preservar histórico**: alterações e exclusões relevantes têm trilha de auditoria; preferência por cancelamento/estorno e reversão quando houver liquidação.
4. **Separar estado e previsão**: realizado, pendente, previsto, vencido e cancelado não podem ser somados indistintamente.
5. **Separar autoria e titularidade**: despesa paga por mim em nome de outra pessoa pode gerar um recebível; transferência de conta própria não é receita.
6. **Regras temporais explícitas**: datas civis no calendário local, horários em UTC quando representarem instantes; faturas calculadas por competência do cartão.
7. **Privacidade single-user**: somente o proprietário usa o aplicativo; contatos cadastrados são registros financeiros, **não** contas com acesso. Nenhum compartilhamento de dados ou workspace de família.
8. **Consistência transacional**: operações de pagamento, transferência, parcelamento e quitação usam transações de banco de dados e idempotência.
9. **Nada de métricas simuladas como reais**: seed/demonstração apenas em banco ou ambiente isolado, nunca misturado ao banco pessoal.
10. **Simplicidade operacional**: não criar RBAC, convites, grupos, times, organizações, planos, assinaturas SaaS, onboarding coletivo ou infraestrutura de multi-tenancy.

---

## 2. Escopo pessoal — único usuário (decisão definitiva)

**O único usuário é o proprietário do sistema.** Não se trata de produto SaaS, plataforma para clientes, controle de várias famílias nem software colaborativo. O banco de dados pertence a uma única pessoa.

### 2.1 Dentro do escopo

- Cadastrar suas **próprias** contas, carteiras, cartões, receitas, gastos, obrigações, objetivos e vencimentos.
- Cadastrar **contatos como contrapartes financeiras**, para registrar que alguém deve dinheiro ao proprietário ou que ele deve a alguém.
- Registrar uma despesa da casa e a parte que cada contato deve reembolsar, sem que ninguém além do proprietário acesse os registros.
- Consultar dashboards, relatórios, calendário, alertas e histórico pessoal, em computador ou celular.
- Proteger o acesso por login **de uma única identidade autorizada** se a aplicação estiver acessível pela internet.

### 2.2 Explicitamente fora do escopo

- Cadastro/registro de outros usuários, convites, equipes, permissões por papéis (RBAC), perfis administrativos, organizações, grupos ou núcleo familiar compartilhado.
- Login de familiares, devedores, credores ou terceiros; cada contato é apenas uma entidade cadastral.
- `household_id`, `tenant_id`, `owner_user_id` repetido em cada tabela para isolamento multi-tenant, tabelas de membros, roles ou convites.
- Compartilhar dashboard, disponibilizar extratos publicamente ou permitir a terceiros marcarem pagamentos.
- Planos pagos, cobrança de assinaturas do aplicativo, gerência de usuários e qualquer lógica de SaaS.

### 2.3 Política de acesso

**Cenário padrão recomendado:** aplicativo web privado, com backend e banco, acessível por celular/desktop, protegido por uma conta autenticada e autorizada, sem registro público. Pode usar um provedor de autenticação gerenciado ou uma camada de acesso confiável, desde que permita **apenas a identidade do proprietário**.

- No banco do domínio financeiro, não é necessária uma tabela `users` nem FKs de usuário em todos os lançamentos. Usar `app_settings` singleton para preferências e configurar a identidade externa autorizada em segredo/ambiente ou tabela privada de controle de acesso.
- Um único perfil de proprietário equivale a **controle de acesso**, não a um sistema de multiusuários. Toda requisição privada confirma a sessão válida e que a identidade autenticada é a permitida.
- Para execução exclusivamente local em `localhost` e sem exposição na rede, login pode ser dispensado por decisão explícita, nunca como default de deploy na internet.
- Se a identidade autorizada mudar, exigir procedimento administrativo seguro; não oferecer na aplicação a função de adicionar usuários.

### 2.4 Decisões de produto para simplificar o MVP

- Um único conjunto de preferências, moeda `BRL`, locale `pt-BR` e timezone `America/Fortaleza` por padrão.
- Entrada **manual de dados**; nenhuma integração bancária, leitura automática de mensagens, Pix real ou pagamento automático.
- Nada de multi-tenancy preparado "para o futuro" sem necessidade demonstrada. A complexidade deve acompanhar o uso real.
- Histórico de pessoas é mantido para **contabilidade de valores a receber/devolver**, não para gerenciamento de membros.

## 3. Navegação e arquitetura da informação

Sidebar desktop (recolhível) e navegação compacta no mobile:

```text
FINANCE HUB
├── Visão geral (Dashboard)
├── Calendário financeiro
├── Lançamentos
│   ├── Todas as movimentações
│   ├── Receitas
│   ├── Despesas
│   └── Transferências
├── Cartões
│   ├── Meus cartões
│   ├── Faturas
│   ├── Compras parceladas
│   └── Pagamentos
├── Contas da casa
│   ├── Fixas e variáveis
│   ├── Mensalidades e assinaturas
│   ├── Reembolsos e divisão informativa
│   └── Histórico de pagamentos
├── Valores com terceiros
│   ├── A receber
│   ├── A pagar / devolver
│   ├── Empréstimos e adiantamentos
│   └── Histórico de acertos
├── Contas e carteiras
├── Planejamento
│   ├── Orçamentos
│   ├── Metas e reservas
│   └── Projeção de fluxo de caixa
├── Relatórios
│   ├── Por categoria
│   ├── Por período
│   ├── Por cartão
│   ├── Por pessoa
│   └── Exportações
├── Notificações
└── Configurações
```

Elementos globais: seletor de mês/período, busca universal, atalho “Novo lançamento”, central de alertas e preferências visuais. **Nenhuma tela de usuários, equipes, convites, grupos ou troca de workspace.**

---

## 4. Dashboard — especificação detalhada

O dashboard é a tela principal **do proprietário**, deve ser útil **antes de qualquer gráfico** e não contém métricas de equipe/usuários. Suportar filtros por período (mês atual, mês anterior, últimos 3/6/12 meses, personalizado), conta, cartão, categoria, pessoa e status. A seleção de período deve refletir em todos os componentes compatíveis, informando quando algum cartão usa competência diferente.

### 4.1 Primeira linha: indicadores (KPIs)

| Indicador | Regra de cálculo | Detalhamento clicável |
|---|---|---|
| Saldo disponível | Soma dos saldos reconciliados de contas líquidas selecionadas | Contas e carteira |
| Receitas realizadas | Entradas classificadas como receita e efetivamente recebidas no período | Lançamentos de receita |
| Despesas realizadas | Consumo/despesas do período conforme base escolhida (caixa ou competência) | Gastos por categoria |
| Contas a vencer | Soma dos compromissos em aberto com vencimento no intervalo | Lista ordenada por vencimento |
| Contas vencidas | Soma de obrigações abertas com `due_date < hoje` | Pendências vencidas |
| Faturas abertas | Saldo não pago por fatura, detalhado por cartão | Faturas |
| Valores a receber | Principal + encargos válidos - liquidações, apenas saldos positivos | Pessoas/devedores |
| Valores a pagar a terceiros | Obrigações de repasse/emprestimo não quitadas | Pessoas/credores |
| Disponível projetado | Saldo líquido atual + entradas previstas - saídas previstas no horizonte | Fluxo de caixa projetado |

**Nota:** estes KPIs **não são todos somáveis entre si**. Por exemplo, uma fatura aberta pode incluir despesas já reconhecidas por competência; o sistema não deve adicioná-la novamente ao total de gastos. Exibir ajuda contextual para base de cálculo.

### 4.1.1 Visão pessoal: prioridades e decisões imediatas

Na abertura, destacar **“Quanto posso gastar hoje?”** sem apresentar um número enganoso: mostrar saldo disponível, obrigações previstas até o próximo recebimento e uma estimativa de **saldo livre após compromissos**. Explicar claramente que o saldo livre é calculado com dados cadastrados, não uma garantia.

Adicionar filtros rápidos **“Este mês”**, **“Próximos 7 dias”**, **“Até o próximo pagamento”**, **“Cartões”** e **“Quem me deve”**. Permitir registrar despesa, compra no cartão, conta a pagar ou empréstimo em um fluxo curto, com campos avançados recolhidos por padrão.

### 4.2 Componentes visuais

1. **Receitas x despesas:** gráfico de barras mensais com alternância entre regime de caixa e competência. Apresentar saldo líquido e tendência.
2. **Evolução do saldo:** linha por dia/semana/mês, com realizado e projeção visualmente distintos.
3. **Despesas por categoria:** gráfico de rosca e tabela de ranking, com percentual e variação em relação ao período anterior; evitar rosca com muitas categorias (agrupar em “Outros”).
4. **Comprometimento dos próximos 30/60/90 dias:** barras empilhadas por faturas, contas domésticas, empréstimos e demais compromissos, com deduplicação de contas que geraram recebíveis/reembolsos.
5. **Utilização dos cartões:** limite usado, limite disponível, fatura atual, próxima fatura, compras parceladas futuras; por cartão.
6. **Calendário de vencimentos:** visão semanal/mensal com marcador de categoria, valor, situação e acesso ao lançamento.
7. **Pendências prioritárias:** vencidas primeiro, depois vencimentos próximos; ação “Marcar como pago” ou “Registrar pagamento”.
8. **Quem me deve / a quem devo:** lista das pessoas com valores em aberto, vencimentos e histórico de liquidação.
9. **Orçamento do mês:** limites por categoria, realizado, previsto e percentual comprometido.
10. **Últimas movimentações:** descrição, data, origem/destino, pessoa, categoria, valor, status, filtro e link para editar.
11. **Comparativo mensal:** mês atual versus anterior e média móvel, sem extrapolar períodos parciais como se fossem meses completos.
12. **Saúde financeira:** métricas descritivas (ex.: taxa de poupança, despesas fixas/receita, obrigações vencidas), sem pontuação arbitrária ou recomendações financeiras automatizadas como se fossem aconselhamento profissional.

### 4.3 Interações e estados

- Cards com navegação para listas filtradas; tooltip de fórmula; variação em R$ e % (retornar `N/A` quando denominador anterior for zero).
- Visões vazias úteis: CTAs para cadastrar conta, cartão, primeira despesa ou mensalidade.
- Skeletons durante carregamento; tratamento de erros e botão de recarregar; últimas atualizações e timezone.
- Em celular: KPIs em grade responsiva, gráficos legíveis e tabelas convertidas em cartões.
- Filtros persistidos na URL; preferências do usuário persistidas separadamente.
- Contraste AA, navegação por teclado, labels acessíveis e suporte a leitores de tela.

---

## 5. Módulo: contas financeiras e carteiras

Tipos: corrente, poupança, dinheiro, carteira digital e outros. Campos: nome, instituição, cor/ícone, saldo inicial, data do saldo inicial, moeda, status ativo/arquivado e observações.

Operações:

- Entrada de receita, pagamento de despesas, transferências e ajustes de conciliação.
- Transferência entre contas próprias com **duas pernas contábeis vinculadas**, origem negativa e destino positiva; não classificar como renda ou despesa.
- Saldo atual = saldo inicial + entradas efetivas - saídas efetivas + ajustes autorizados.
- Despesas e receitas futuras **não** alteram saldo atual; alteram somente projeções.
- Contas arquivadas preservam histórico e não recebem novos lançamentos sem reativação.
- Reconciliar saldo apurado com extrato informado e criar ajuste identificado, nunca alterar saldo inicial silenciosamente.

---

## 6. Módulo: cartões de crédito

### 6.1 Cadastro de cartão

Campos: nome, banco/emissor, apelido, últimos quatro dígitos **opcionais**, bandeira **opcional**, limite total em centavos, dia de fechamento, dia de vencimento, política de competência, cor, conta padrão para pagamento e estado.

**Nunca solicitar ou armazenar:** número completo do cartão, CVV, senha ou credenciais bancárias. Este sistema não processa transações com cartão.

### 6.2 Faturas e competência

Cada cartão possui ciclos de fatura definidos pelas datas **efetivas** de abertura/fechamento; a data de vencimento deriva da configuração e é editável por ciclo. Implementar uma função determinística `resolve_statement_for_purchase(card_id, purchase_date)` que encontre o ciclo cujo intervalo de compras contém a data.

Regras:

- `closing_day` e `due_day` são configurações, **não** suposição de que vencimento cai sempre no mesmo mês.
- Para meses com menos dias: política explícita, por padrão utilizar o último dia do mês. Registrar a data real do ciclo gerado.
- A regra de qual ciclo vence em qual mês precisa ser configurável por cartão (por exemplo: fechamento dia 25, vencimento no dia 5 do mês seguinte).
- Alteração no dia de fechamento afeta **apenas novos ciclos**; ciclos históricos preservam datas materializadas.
- Compras no fechamento pertencem a um ciclo conforme regra configurável, documentada e testada; adotar no MVP intervalo `[início, fechamento)` com datas civis e expor qual fatura receberá a compra antes da confirmação.
- Faturas podem ser `OPEN`, `CLOSED`, `PARTIALLY_PAID`, `PAID`, `OVERDUE`, `CANCELLED` (cancelamento apenas em casos válidos); idealmente status derivado dos valores e datas.
- O limite consumido depende de lançamentos não estornados e amortizações efetivas; não confundir saldo da fatura corrente com utilização global do limite.

### 6.3 Compras à vista e parceladas

Campos: descrição, estabelecimento, compra em `date`, total, quantidade de parcelas, taxa/juros **opcionais**, categoria, pessoa responsável, observações, anexo futuro, cartão e estado.

- Compra à vista corresponde a 1 parcela.
- Compra parcelada gera um contrato de compra e N parcelas associadas a ciclos consecutivos, seguindo a competência da primeira parcela.
- Dividir centavos sem perda: `valor_base = floor(total_centavos/N)`; distribuir o resto com +1 centavo nas primeiras parcelas. Soma das parcelas deve ser exatamente o total.
- Ex.: R$ 100,00 em 3 vezes → R$ 33,34 + R$ 33,33 + R$ 33,33.
- Juros precisam estar discriminados e adicionados somente uma vez ao montante financiado; registrar total contratado versus valor à vista.
- Estorno parcial ou total: criar reversões vinculadas, com política de alocação a faturas, sem apagar parcelas pagas.
- Antecipação de parcelas: transação específica; **não** apenas trocar data sem atualizar alocação e limite.
- Não permitir edição do valor original de compra que já tem pagamentos irreversíveis sem fluxo de correção auditado.

### 6.4 Pagamento da fatura

O pagamento registra `statement_payment` (valor, data, conta de origem, identificador idempotente) e gera saída efetiva da conta bancária. Aceitar pagamento integral ou parcial, sem ultrapassar saldo devido salvo fluxo explícito de crédito em fatura.

**Evitar dupla contagem:**
- Visão **consumo por competência**: compras categorizadas (à vista/parcelas conforme política selecionada), sem contar pagamento de fatura como nova despesa.
- Visão **caixa**: pagamentos de faturas como saídas efetivas da conta, mas compras em cartão não debitem banco antecipadamente.
- Identificar claramente a base do relatório; o mesmo pagamento não pode entrar como consumo e saída adicional no mesmo total.

### 6.5 Tela detalhada do cartão

Cabeçalho: limite total, utilizado, disponível, próximo fechamento, vencimento e valor da fatura. Abas: faturas (passadas/atual/próximas), compras, parcelas futuras, pagamentos, configurações e histórico.

---

## 7. Módulo: despesas da casa, mensalidades e assinaturas

### 7.1 Categorias iniciais (editáveis)

Moradia: aluguel, condomínio, energia, água, gás, internet, telefone, IPTU.
Alimentação: mercado, feira, delivery.
Transporte: combustível, manutenção, transporte público.
Educação: faculdade, cursos, material.
Saúde: consultas, medicamentos, plano.
Assinaturas: streaming, software, academia.
Outros: lazer, pets, compras, imprevistos.

### 7.2 Lançamentos avulsos

Campos: descrição, categoria, valor, competência, vencimento, data de pagamento, conta ou cartão, favorecido, pessoa responsável, status (`PLANNED`, `PENDING`, `PARTIALLY_PAID`, `PAID`, `OVERDUE`, `CANCELLED`), comprovante futuro, observações e tags.

Vencimento é propriedade da **obrigação**, pagamento é um **evento**; guardar ambos. Permitir pagamento parcial, múltiplos pagamentos e histórico de mudanças.

### 7.3 Recorrências

- Frequências: semanal, quinzenal, mensal, bimestral, trimestral e anual (regras explícitas).
- Definir dia-alvo, início, término opcional, forma de pagamento padrão, categoria e política de feriados/vencimento.
- Gerar ocorrências com antecedência configurável, por job idempotente, com chave única por regra + competência.
- Editar “somente esta ocorrência”, “esta e futuras” (versionamento da regra) ou “todas as futuras”.
- Casos de mensalidade reajustada: preservar histórico antigo e aplicar novo valor somente a partir da data efetiva.
- Contas variáveis (energia, água): gerar **estimativa provisória**; substituir pelo valor real quando informado, mantendo trilha de alteração e distinção estimado/confirmado.
- Lembretes em D-7, D-3, D-1, D0 e atraso (configuráveis). Lembrete não significa pagamento.

### 7.4 Rateio da casa — controle privado e manual

Uma despesa pode ser distribuída por valores fixos, percentuais ou partes iguais entre **contatos cadastrados, sem acesso próprio ao sistema**. Exigir soma das participações = valor final (corrigir arredondamento em centavos). Exibir “quem pagou”, “quem deve reembolsar” e “quanto já foi repassado”.

Exemplo: internet R$ 120,00, paga por uma pessoa e dividida 50/50 → despesa da casa R$ 120,00, pagamento bancário R$ 120,00, **recebível de R$ 60,00** contra o outro morador. Receber R$ 60,00 reduz esse recebível e adiciona R$ 60,00 à conta bancária, **não** gera nova receita operacional ou segunda despesa de internet. Relatório pessoal pode mostrar, lado a lado, **despesa bruta de R$ 120,00** e **custo líquido pessoal de R$ 60,00 após reembolso confirmado**, sem alterar retroativamente a despesa original.

---

## 8. Módulo: valores passados, empréstimos, adiantamentos e acertos

**“Valor passado” é ambíguo:** tratar explicitamente operações diferentes para não classificar tudo como empréstimo. **Todas as pessoas envolvidas são contatos cadastrados pelo proprietário; não criam conta nem acessam o aplicativo.**

### 8.1 Tipos de operação

| Tipo | Exemplo | Impacto correto |
|---|---|---|
| Empréstimo concedido | Emprestei R$ 200 a alguém | Sai dinheiro; cria R$ 200 a receber; não é despesa de consumo |
| Empréstimo tomado | Alguém me emprestou R$ 300 | Entra dinheiro; cria R$ 300 a devolver; não é receita de trabalho |
| Adiantamento/reembolso | Paguei R$ 80 por outra pessoa | Saída da conta e direito a reembolso; identificar despesa original e parcela reembolsável |
| Repasse de despesa compartilhada | Outra pessoa paga sua parte da conta de luz | Reduz recebível, entrada de caixa, não nova receita |
| Transferência entre minhas contas | Enviei R$ 500 do banco A ao B | Duas movimentações vinculadas, patrimônio total inalterado |
| Transferência sem obrigação | Dei R$ 50 a um familiar | Saída definitiva classificada como transferência/doação pessoal, sem recebível |
| Valor que vou pagar a alguém | Estou devendo R$ 120 de uma compra | Passivo a pagar; quitação reduz o passivo |

### 8.2 Registro de obrigação com terceiro

Campos: pessoa, tipo, descrição, principal, encargos/juros opcionais, data da operação, vencimento opcional, origem do dinheiro, conta financeira, parcelas combinadas opcionais, responsável, status, comprovante futuro e observações.

- Status derivado: `OPEN`, `PARTIALLY_SETTLED`, `SETTLED`, `OVERDUE`, `CANCELLED`.
- Suportar liquidações parciais, datas distintas, correções, descontos, perdão de dívida e estorno com justificativa.
- `saldo_em_aberto = principal + encargos confirmados - descontos confirmados - liquidações líquidas`, não negativo sem operação especial de crédito.
- Empréstimo a receber não vira receita na concessão; recebimento do principal não vira receita novamente. Juros efetivamente recebidos podem compor receita financeira separada.
- Empréstimo tomado não é receita na entrada; devolução do principal não é despesa de consumo. Juros pagos podem ser despesa financeira.
- Pagamentos e recebimentos de terceiros devem estar vinculados à conta e refletir no saldo bancário quando efetivamente liquidados.

### 8.3 Tela por pessoa

Visão consolidada privada do proprietário: valores que o contato me deve, valores que devo ao contato, saldo líquido **apenas informativo**, lista de operações com sua natureza, histórico de acertos, próximos vencimentos e exportação. **Não compensar dívidas opostas automaticamente**; compensação exige evento explícito autorizado.

---

## 9. Calendário financeiro e alertas

Visualizações: mês, semana, agenda e “próximos vencimentos”. Eventos: vencimentos de faturas, contas da casa, recorrências, parcelas, compromissos com terceiros e receitas previstas.

Filtros: origem, status, valor, categoria, pessoa. Cores + texto/ícone de status (não depender apenas de cor).

Alertas internos:
- Vencimentos D-7/D-3/D-1/D0 e vencidos.
- Fatura acima de um limite de utilização configurável (ex.: 80%).
- Orçamento de categoria em 80%, 100% e ultrapassado.
- Despesa recorrente prevista ainda não confirmada.
- Recebível vencido; compromisso com terceiro próximo do vencimento.

Notificações por email/push são **fase posterior** e exigem consentimento, preferências e serviço de entrega. No MVP, central de alertas in-app é suficiente.

---

## 10. Orçamentos, metas e projeções

**Orçamentos** por categoria e período, com teto nominal, progresso, saldo restante, realizado e comprometido. Escolher se o orçamento acompanha **competência de consumo** ou **caixa** e documentar cada métrica. Não somar uma transferência interna aos gastos.

**Metas**: reserva de emergência, viagem, aquisição etc. Meta tem valor-alvo, prazo opcional e aportes rastreáveis; aportes entre contas próprias não representam gasto.

**Projeção**: saldo inicial líquido confirmado + recebimentos previstos (com política configurável de inclusão) - desembolsos previstos, evitando somar parcela de cartão e fatura futura como duas saídas. Em caixa, o evento projetado para compras de cartão é o **pagamento da fatura**, não cada parcela novamente.

Cenários: conservador (somente receitas confirmadas e obrigações conhecidas), base (recorrências e previsões registradas), personalizado. Rotular projeções como estimativas, nunca como saldo garantido.

---

## 11. Relatórios, filtros e exportações

- Gastos por categoria e subcategoria, com drill-down.
- Gastos por cartão, competência, estabelecimento e parcelamento.
- Histórico mensal de receitas, despesas, saldo líquido e variações.
- Contas da casa: valor previsto x realizado, pagamentos em atraso, rateios e reembolsos.
- Terceiros: valores em aberto por pessoa, aging de recebíveis (0–30, 31–60, 61–90, 90+ dias), liquidações.
- Calendário de obrigações e pagamentos.
- Fluxo de caixa realizado e previsto por dia/mês.
- Exportações CSV UTF-8 (com BOM opcional para Excel), XLSX e PDF em fases progressivas.
- Exportar somente a partir de sessão validada do proprietário; registrar histórico de exportação quando contiver dados sensíveis.

Filtros combináveis com datas inicial/final, categoria, pessoa, conta, cartão, status, tags e busca textual. Totalizadores sempre usam exatamente o mesmo conjunto filtrado mostrado na lista.

---

## 12. Fluxos críticos de ponta a ponta

### Fluxo A — Cadastrar e pagar conta recorrente

1. Criar regra “Internet”, R$ 120,00, todo dia 10, débito em conta.
2. Gerar ocorrência para o mês, status pendente, exibida no calendário e KPI de vencimentos.
3. Registrar pagamento na conta bancária em 9/12; criar lançamento efetivo vinculado.
4. Atualizar saldo bancário, ocorrência e dashboard; nenhum evento duplicado.
5. Preservar evento mensal seguinte como obrigação independente.

### Fluxo B — Compra parcelada no cartão

1. Registrar compra de R$ 600 em 6x, data e cartão.
2. Resolver ciclo inicial; gerar 6 parcelas de R$ 100 em ciclos sucessivos.
3. Exibir parcela na fatura correta, compromisso de meses futuros e limite utilizado.
4. Pagar primeira fatura: debitar banco e reduzir saldo devido da fatura, sem duplicar gastos por categoria.
5. Se houver estorno, aplicar reversão contabilmente explícita e reconciliar faturas afetadas.

### Fluxo C — Emprestei dinheiro e recebi parcialmente

1. Conceder R$ 300 para pessoa X saindo de uma conta bancária.
2. Criar obrigação `RECEIVABLE` de R$ 300; reduzir saldo da conta R$ 300; não aumentar “despesas de consumo”.
3. Registrar R$ 100 recebidos; elevar saldo bancário R$ 100 e reduzir a receber para R$ 200.
4. Exibir R$ 200 no dashboard e no cadastro da pessoa, com histórico auditável.

### Fluxo D — Conta da casa com rateio

1. Registrar luz R$ 240 paga por mim, dividida entre 3 pessoas: R$ 80 cada.
2. Registrar uma única despesa de R$ 240 e um único pagamento.
3. Criar dois recebíveis de R$ 80 vinculados ao rateio (não três despesas novas).
4. Cada repasse recebido reduz o recebível correspondente e aumenta saldo bancário.

### Fluxo E — Transferência interna

1. Transferir R$ 500 entre duas contas minhas.
2. Gerar operações de origem e destino na mesma transação de banco.
3. Saldo total consolidado permanece idêntico; relatório de receita/despesa não é alterado.

---

## 13. Modelo de dados sugerido — banco single-user

**Banco:** PostgreSQL. Adotar UUID, `created_at`, `updated_at` e `version` quando relevante para concorrência. **Não criar `users`, `roles`, `members`, `households`, `tenants`, `invitations`, `owner_user_id`, `household_id` ou `tenant_id` nos registros financeiros**. Há um banco lógico pessoal único. O acesso é controlado na borda HTTP e na infraestrutura, nunca por cadastro de outros usuários.

| Tabela | Campos-chave / papel |
|---|---|
| `app_settings` | chave singleton, locale, timezone, tema, moeda, preferencias_alertas, defaults_dashboard |
| `financial_accounts` | id, name, type, currency, opening_balance_cents, opening_date, archived_at |
| `persons` | id, display_name, contact_optional, notes (contatos financeiros, **sem login**) |
| `categories` | id, parent_id, name, kind, color, archived_at |
| `transactions` | id, account_id, amount_cents (assinado), kind, effective_date, occurred_at, status, category_id, counterparty_id, source_type, source_id, transfer_group_id, idempotency_key |
| `obligations` | id, type, title, category_id, expected_amount_cents, due_date, competence_month, status, recurrence_occurrence_id, related_party_id |
| `obligation_settlements` | id, obligation_id, transaction_id, applied_amount_cents, applied_at, reversed_at |
| `recurrence_rules` | id, template, frequency, interval, anchor_day, starts_on, ends_on, generation_horizon, version, state |
| `recurrence_occurrences` | id, rule_id, rule_version, competence_month, due_date, obligation_id, estimated, unique occurrence key |
| `credit_cards` | id, name, limit_cents, closing_day, due_day, due_month_offset, purchase_boundary_policy, default_payment_account_id |
| `card_statements` | id, card_id, cycle_start_date, cycle_end_exclusive, due_date, status, unique(card_id, cycle_start_date) |
| `card_purchases` | id, card_id, purchased_on, description, category_id, total_cents, installments_count, state, person_id |
| `card_installments` | id, purchase_id, statement_id, installment_number, amount_cents, state, unique(purchase_id, installment_number) |
| `statement_payments` | id, statement_id, transaction_id, amount_cents, paid_on, idempotency_key |
| `party_balances` | id, person_id, direction (`RECEIVABLE`/`PAYABLE`), origin_type, origin_id, principal_cents, confirmed_charges_cents, discounts_cents, due_date, state |
| `party_settlements` | id, party_balance_id, transaction_id, amount_cents, settled_on, reversal_id |
| `expense_splits` | id, obligation_id, payer_person_id nullable, person_id, share_amount_cents, receivable_id nullable |
| `budgets` | id, category_id, period_start, period_end, limit_cents, basis |
| `goals` | id, title, target_cents, target_date, state |
| `goal_allocations` | id, goal_id, transfer_reference, amount_cents, allocated_on |
| `notifications` | id, event_type, entity_type, entity_id, scheduled_for, read_at, sent_at, unique key |
| `attachments` | id, related_type, related_id, storage_key, mime_type, size_bytes |
| `audit_events` | id, entity_type, entity_id, operation, before_json, after_json, occurred_at, request_id, actor='owner' |

### 13.1 Observações importantes de modelagem

- `transactions` é o livro de **movimentações de caixa**. Compras no cartão e obrigações futuras **não** são transações de caixa até liquidadas. Não criar transação bancária fictícia para cada parcela.
- `obligations` representam obrigações genéricas fora do cartão; faturas e parcelas têm modelo próprio. Criar uma **visão de compromissos unificados** para calendário e projeções, com chave de deduplicação por origem.
- Estado da fatura e da obrigação pode ser derivado de saldo, vencimento e reversões, com snapshot materializado somente quando necessário.
- `expense_splits` deve referenciar a despesa original e os recebíveis resultantes; impedir vínculo duplicado. Os contatos não são usuários, mesmo que participem dos rateios.
- `statement_payments.transaction_id` e `party_settlements.transaction_id` exigem relacionamento consistente, operações transacionais e autorização da sessão única.
- Mesmo se houver exclusão lógica, índices únicos e reprocessamento devem considerar a política de cancelamento/reversão.
- Para garantir **consistência referencial financeira**, operações de caixa devem ser geradas por serviços de domínio, não diretamente por CRUD genérico.
- `app_settings` deve ter **exatamente um registro** ou ser modelada como coleção chave-valor validada; não criar perfis de diferentes usuários.

### 13.2 Constraints e integridade

- Montantes originais > 0 onde aplicável; parcela N entre 1 e total.
- Soma de parcelas = total da compra; soma dos rateios = valor devido.
- Saldo em aberto não pode ficar negativo (exceto crédito explícito modelado separadamente).
- Limite disponível pode ser negativo se uso ultrapassou limite após ajustes; não mascarar valores.
- Uma ocorrência por regra/versão/competência (ou chave estável de ocorrência equivalente).
- Não há chaves de multi-tenancy ou verificações cruzadas entre usuários; em vez disso **recusar toda requisição não autenticada ou autenticada com identidade diferente da do proprietário**.
- IDs das entidades financeiras não devem ser acessíveis sem sessão válida, mesmo com URL conhecida.
- Ações financeiras sensíveis devem ser atômicas e idempotentes.

## 14. Arquitetura técnica proposta

### 14.1 Stack recomendada

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Frontend | React + TypeScript + Vite | SPA responsiva, manutenção simples |
| UI | Tailwind CSS + shadcn/ui | Componentização e acessibilidade, customização visual |
| Formulários | React Hook Form + Zod | Validação declarativa e mensagens consistentes |
| Dados remotos | TanStack Query | Cache, refetch e invalidação controlada |
| Gráficos | Recharts ou equivalente | Dashboards interativos |
| Backend | Python + FastAPI + Pydantic | Serviços e contratos explícitos de domínio |
| ORM / migrações | SQLAlchemy + Alembic | Modelagem, transações e evolução do schema |
| Banco | PostgreSQL | Integridade e cálculos financeiros consistentes |
| Autenticação | Uma única identidade autorizada (JWT/OIDC, access proxy ou serviço gerenciado) | Login privado sem registro público, papéis ou permissões por equipe |
| Testes | Pytest + testes frontend + Playwright | Regras financeiras, UI e E2E |
| Infra | Docker Compose para desenvolvimento | Ambiente reproduzível |

**Não criar sistema de contas de usuários.** Se utilizar Supabase Auth, desabilitar registro público e verificar no backend que `sub` corresponde **exatamente** à única identidade autorizada em configuração segura; nenhuma chave de serviço deve aparecer no navegador. Preferir operações financeiras sempre via FastAPI. Não implementar RLS por grupos/tenants, nem tabela de membros. Caso a aplicação seja exclusivamente local, avaliar modo sem login com restrição rigorosa a `localhost` e nunca expor isso à internet.

### 14.2 Módulos de domínio backend

```text
backend/
  app/
    main.py
    core/
      config.py
      owner_access.py  # validar unica identidade permitida
      security.py
      database.py
      errors.py
      logging.py
    api/v1/
      router.py
      dashboard.py
      accounts.py
      transactions.py
      cards.py
      statements.py
      household_bills.py
      recurrences.py
      people.py  # contatos, nao usuarios
      settlements.py
      budgets.py
      reports.py
      notifications.py
    domains/
      accounts/
      ledger/
      cards/
      obligations/
      recurrences/
      counterparties/
      budgeting/
      reporting/
    models/
    schemas/
    repositories/
    services/
    jobs/
    tests/
  alembic/
  pyproject.toml
frontend/
  src/
    app/
    pages/
    features/
      dashboard/
      accounts/
      transactions/
      cards/
      bills/
      people/
      budget/
      reports/
    components/
      ui/
      charts/
      finance/
    hooks/
    lib/
      api/
      money/
      date/
    types/
    tests/
  package.json
infra/
  compose.yml
docs/
  ARCHITECTURE.md
  FINANCIAL_RULES.md
  API_CONTRACTS.md
  DECISIONS.md
.env.example
README.md
```

Separar regras de domínio do transporte HTTP. O frontend não é autoridade para calcular saldo, fatura, limites ou liquidação.

### 14.3 Fluxo de processamento

`Frontend → validação da sessão e identidade do proprietário → API privada → serviço de aplicação → regra de domínio → transação PostgreSQL → auditoria → resposta → invalidação de cache → dashboard`.

Jobs de recorrência e lembretes devem ser idempotentes; executar agendamento no servidor e monitorar falhas. Não depender de o navegador estar aberto.

---

## 15. Contratos API (rascunho)

Base `/api/v1`. JSON, **autenticação da única identidade permitida** em toda rota financeira quando hospedada, paginação com `limit` e cursor ou página, filtros validados. **Não criar endpoints de registro de usuário, membros, equipes, convites, papéis ou organizações.** Retornar valores monetários como **strings decimais** (`"120.00"`) ou campos em centavos explicitamente sufixados (`amount_cents`); escolher um contrato único e documentar no OpenAPI.

| Método | Endpoint | Objetivo |
|---|---|---|
| GET | `/dashboard?from=&to=&basis=` | KPIs, gráficos e alertas agregados |
| GET/POST | `/accounts` | Listar/cadastrar contas |
| GET | `/accounts/{id}/ledger` | Extrato e saldo |
| POST | `/transfers` | Transferir entre contas próprias |
| GET/POST | `/transactions` | Lançamentos de caixa |
| GET/POST | `/cards` | Cartões |
| GET | `/cards/{id}/statements` | Histórico de faturas |
| GET | `/statements/{id}` | Detalhe e parcelas |
| POST | `/cards/{id}/purchases` | Comprar à vista ou parcelado |
| POST | `/statements/{id}/payments` | Pagamento parcial/integral |
| GET/POST | `/obligations` | Contas da casa e obrigações |
| POST | `/obligations/{id}/settlements` | Registrar pagamento |
| GET/POST | `/recurrences` | Regras de recorrência |
| GET/POST | `/people` | Contatos financeiros (não usuários) |
| GET/POST | `/party-balances` | Valores a receber/devolver |
| POST | `/party-balances/{id}/settlements` | Acerto parcial/integral |
| GET | `/calendar?from=&to=` | Eventos unificados sem duplicidade |
| GET/POST | `/budgets` | Orçamentos |
| GET | `/reports/cash-flow` | Fluxo de caixa |
| GET | `/reports/categories` | Consumo por categoria |
| GET | `/reports/counterparties` | Posição de terceiros |
| GET | `/notifications` | Alertas e avisos |
| POST | `/notifications/{id}/read` | Marcar leitura |
| GET | `/exports/transactions.csv` | CSV autorizado |

### 15.1 Exemplos de payload

**Criar compra parcelada**

```json
{
  "card_id": "uuid-do-cartao",
  "description": "Notebook",
  "purchase_date": "2026-11-24",
  "total_amount_cents": 299999,
  "installments": 10,
  "category_id": "uuid-da-categoria"
}
```

**Registrar recebimento parcial**

```json
{
  "party_balance_id": "uuid-da-divida",
  "account_id": "uuid-da-conta",
  "amount_cents": 10000,
  "settled_on": "2026-11-24",
  "idempotency_key": "uuid-unico-da-operacao"
}
```

Respostas de erro padronizadas com código de domínio, `message`, `details` e `request_id`, sem vazamento de detalhes internos. Usar `409` para conflito de versão/idempotência divergente e validações apropriadas para valores impossíveis.

---

## 16. Design system e experiência visual

**Direção:** dashboard financeiro profissional, sóbrio, com densidade informativa controlada. Não replicar visual genérico de banco digital nem usar excesso de gradientes.

- Tema claro e escuro, com preferência persistente; dark mode com contraste real.
- Paleta base neutra (grafite, off-white) com cor de destaque única configurável; verde para entrada/posição favorável e vermelho para atraso/saída, **sempre com rótulos e sinais**.
- Tipografia legível; números tabulares (`font-variant-numeric: tabular-nums`).
- Componentes: `MoneyInput`, `CurrencyDisplay`, `PeriodPicker`, `StatusBadge`, `DueDateChip`, `FinancialKpi`, `CardUtilization`, `TransactionTable`, `PaymentDialog`, `InstallmentTimeline`, `EmptyState`, `ConfirmActionDialog`.
- Mobile-first para consulta e registro rápido; desktop para análise detalhada.
- Modais para ações rápidas; páginas próprias para fluxos complexos.
- Formulários com máscara visual BRL, mas parse seguro para centavos e validação no backend.
- Datas e valores pt-BR exibidos como `24/11/2026` e `R$ 1.234,56`; timestamps serializados em ISO 8601 com fuso.
- Feedback de sucesso/erro específico e confirmação para pagamento, estorno, cancelamento e exclusão.
- Recharts não devem ser única fonte dos números: ter tabelas acessíveis e textos equivalentes.

### 16.1 Wireframe lógico do dashboard

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ Logo / Busca              Período ▼       + Novo lançamento     Alertas │
├─────────────────────────────────────────────────────────────────────────┤
│ Saldo disponível  │ Receitas │ Despesas │ A vencer │ Vencidas          │
│ Faturas abertas   │ A receber          │ A devolver │ Projeção 30 dias │
├────────────────────────────────┬────────────────────────────────────────┤
│ Receitas x despesas            │ Evolução do saldo                      │
├────────────────────────────────┼────────────────────────────────────────┤
│ Gastos por categoria           │ Cartões e utilização                   │
├────────────────────────────────┼────────────────────────────────────────┤
│ Próximos vencimentos           │ Valores com terceiros                  │
├────────────────────────────────┼────────────────────────────────────────┤
│ Orçamentos e metas             │ Calendário financeiro                  │
├────────────────────────────────┴────────────────────────────────────────┤
│ Últimas movimentações                                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 17. Segurança, privacidade e confiabilidade — acesso de proprietário único

1. **Uso individual não é acesso sem segurança**: se hospedado e acessível via internet, todas as rotas privadas exigem sessão válida e comparação da identidade autenticada com **um único `owner_subject` autorizado** em configuração segura.
2. **Nenhum cadastro público**: proibir sign-up, criação de usuários, convite, redefinição de acesso por terceiros e endpoint de administração de usuários. Não implementar papéis (RBAC), grupos ou multi-tenancy.
3. Todos os dados financeiros pertencem ao único proprietário. `persons` é catálogo de contatos sem login. APIs não aceitam `owner_user_id` ou `tenant_id` em payloads.
4. Bloquear IDOR/BOLA: ids de contas, cartões, faturas, comprovantes e contatos jamais são acessíveis sem a sessão autorizada. Aplicar rate limit para autenticação e ações críticas, CORS restritivo, cabeçalhos seguros e validação de payload.
5. Gerenciar segredos via variáveis de ambiente/secret manager; nunca enviar token de serviço ou credenciais do banco ao frontend.
6. Preferir provedor de autenticação confiável, sessão segura com expiração, MFA quando disponível e gerenciamento cuidadoso de cookies/tokens. Não inventar autenticação caseira.
7. Logs sem dados bancários desnecessários; comprovantes e informações de contatos devem permanecer privados.
8. Backup automático criptografado, teste periódico de restauração, exportação de backup pessoal e política explícita de retenção. Não presumir que deploy gratuito garante backup.
9. Possibilitar exportação e exclusão dos próprios dados. Considerar deveres de privacidade aplicáveis, sem criar módulo de gestão de consentimentos para clientes inexistentes.
10. Manter auditoria dos eventos financeiros, pagamentos, estornos, mudanças de regras e importações; autoria é o proprietário e origem técnica do evento, não outros usuários.
11. Isolamento transacional para operações concorrentes: travas/versão otimista quando necessário e constraints SQL. Mesmo um único usuário pode abrir múltiplas abas/dispositivos.
12. `idempotency_key` em pagamentos, transferências e liquidações para impedir registros duplicados por retry ou clique duplo.
13. Anexos futuros: upload restrito, MIME/size allowlist, armazenamento privado e URLs de duração limitada.
14. Não expor o PostgreSQL publicamente; HTTPS obrigatório em deploy remoto; privilégios mínimos para conexões e migrações.

## 18. Testes obrigatórios e critérios de aceite

### 18.1 Testes unitários de domínio

- R$ 100,00 / 3 parcelas = 33,34 + 33,33 + 33,33.
- Vencimento em dia 31: janeiro para fevereiro considera último dia segundo política.
- Compra exatamente no fechamento entra no ciclo previsto pela política documentada.
- Alteração do fechamento não modifica fatura histórica.
- Pagamento parcial de fatura atualiza saldo devido sem duplicar despesa.
- Transferência entre contas preserva soma dos saldos.
- Empréstimo concedido diminui caixa e eleva recebível, sem elevar despesas categorizadas.
- Pagamento parcial de empréstimo reduz corretamente saldo em aberto.
- Rateio da conta doméstica gera recebíveis cuja soma é igual à soma das parcelas devidas pelos demais participantes.
- Duas chamadas com a mesma chave de idempotência e payload geram um só evento.
- Chave de idempotência repetida com payload diferente retorna conflito.
- Geração recorrente repetida não produz duplicata.
- Estorno desfaz apenas impactos financeiros afetados e mantém trilha de auditoria.
- Requisição sem sessão e requisição autenticada por qualquer identidade diferente do proprietário retornam acesso negado; não existe cadastro de usuário adicional.
- Projeção de caixa não soma parcela de cartão com pagamento da mesma fatura.

### 18.2 Testes de integração/E2E

- Acesso privado do proprietário → criação de conta financeira → lançamento → dashboard atualizado.
- Cartão → compra parcelada → fatura → pagamento → banco reconciliado.
- Mensalidade → geração da ocorrência → aviso → pagamento → histórico.
- Rateio → recebível → repasse parcial → quitação.
- Filtros do dashboard → drill-down → exportação coerente.
- Requisições simultâneas para quitação impedem overpayment.
- Acessibilidade básica e responsividade em 360px, 768px e 1440px.

### 18.3 Definição de pronto (DoD)

Uma funcionalidade está pronta quando inclui: schema/migração, domínio, API, validação, autorização, UI, estado vazio/loading/erro, testes automatizados, auditoria quando aplicável e atualização da documentação. Não considerar “pronto” apenas porque a tela funciona com dados mockados.

---

## 19. Plano de desenvolvimento incremental

### Etapa 0 — Descoberta e documentação (sem código)

- Inspecionar estrutura existente do repositório, stack e convenções.
- Descrever modelo de domínio, decisões de competência/caixa, ciclos de cartão e recebíveis.
- Elaborar DER, contratos de API, riscos e dependências.
- Listar dúvidas *bloqueantes* e adotar defaults justificados para decisões não bloqueantes.
- Submeter plano antes da implementação.

**Entrega:** `docs/ARCHITECTURE.md`, `docs/FINANCIAL_RULES.md`, `docs/DECISIONS.md` e backlog priorizado.

### Etapa 1 — Fundação operacional do MVP

- Controle de acesso para **uma identidade autorizada**, PostgreSQL, migrations, Docker Compose, CI básica; sem sistema de usuários.
- Layout, navegação, contas/carteiras, categorias, pessoas.
- Lançamentos de caixa, transferências, saldos e dashboard inicial real.
- Testes de bloqueio a acessos não autorizados, identidade diferente da permitida e idempotência.

**Aceite:** registrar receitas, despesas e transferência sem inconsistência no saldo.

### Etapa 2 — Cartões e faturas

- Cadastro de cartões, geração de ciclos, compras, parcelamento, faturas, pagamentos.
- Dashboard com limite utilizado e próximos vencimentos.
- Testes de fechamento, competência, parcelas e deduplicação.

**Aceite:** fluxo integral de compra parcelada e pagamento de fatura reconciliado.

### Etapa 3 — Contas da casa e recorrências

- Contas avulsas, regras de recorrência, mensalidades, status e calendário.
- Contas variáveis com estimativa/real, alertas in-app.
- Rateios simples com **contatos sem login**, apenas para apuração dos reembolsos do proprietário.

**Aceite:** criar mensalidade, gerar próximas ocorrências, registrar pagamento sem replicação.

### Etapa 4 — Valores com terceiros

- Empréstimos concedidos/tomados, adiantamentos, reembolsos, repasses.
- Acertos parciais e histórico por pessoa.
- Dashboard de valores a receber/a pagar.

**Aceite:** registrar empréstimo e reembolso sem distorcer receita/despesa.

### Etapa 5 — Inteligência financeira e acabamento

- Orçamentos, metas, projeções 30/60/90 dias, comparativos e relatórios.
- CSV/XLSX/PDF progressivos, filtros refinados, responsividade, acessibilidade.
- Performance das consultas, observabilidade, backup e restore testado.

### Pós-MVP (não bloquear primeira versão)

- Notificações pessoais por email/push e integrações com o calendário pessoal (sem compartilhamento).
- Importação OFX/CSV com conciliação e deduplicação.
- Open Finance via provedor autorizado, se houver justificativa e requisitos regulatórios atendidos.
- OCR de boletos/comprovantes, com revisão humana obrigatória.
- Assistente financeiro por IA **somente como camada interpretativa**, sem criar pagamentos ou alterar registros sem confirmação explícita e trilha de auditoria.

---

## 20. Indicadores de qualidade e desempenho

Metas iniciais **de engenharia, não promessas de produção**:

- Dashboard com agregações de até 10 mil lançamentos pessoais: p95 de API preferencialmente < 500 ms em ambiente controlado, medir e ajustar.
- Pesquisa paginada em vez de baixar todo o histórico.
- Disponibilidade de testes críticos de domínio na CI antes de merge.
- Zero transações duplicadas em testes de retry/idempotência.
- Cobertura prioritária de todas as regras de negócio de dinheiro, especialmente parcelamento e liquidação.
- Processamento de recorrências reexecutável sem duplicidade.
- Monitorar falhas de jobs, erros HTTP, latência das consultas e divergências de saldo.

---

## 21. Dados demo (somente modo demonstração)

Criar seed **opcional**, isolado de produção e claramente identificado como exemplo, com:

- Conta corrente R$ 4.500,00 e carteira R$ 150,00.
- Dois cartões com limites e ciclos distintos.
- Aluguel, energia, internet, faculdade, academia e streaming recorrentes.
- Compra de R$ 1.200,00 em 6x e outra à vista no crédito.
- Empréstimo de R$ 300 concedido, R$ 100 já recebido.
- Despesa de internet de R$ 120 rateada entre duas pessoas.
- Vencimentos futuros e uma obrigação fictícia em atraso.

**Não contaminar métricas reais**. Seeds apenas em **banco de dados ou ambiente de demonstração separado**. Não criar tenant demo ou sistema de multi-tenancy para isso.

---

## 22. Regras de UX financeira a validar com o produto

Antes da codificação do módulo respectivo, documentar:

1. Regime padrão do dashboard: **caixa** nos saldos e fluxos; **competência** para consumo por categoria, com alternância clara.
2. Se limites de cartão consideram compra integral imediatamente e como estornos/pagamentos liberam limite conforme o emissor.
3. Política de compras na data de fechamento e deslocamento do vencimento para dias não úteis.
4. Como juros, multa e pagamento mínimo de cartão são representados (no MVP, registrar encargos reais; **não** inferir encargos bancários).
5. Como distinguir dívida informal de reembolso de despesa já categorizada.
6. Política de editar lançamentos financeiros já liquidados (preferir correção por estorno).
7. Como tratar contas com moedas diferentes: **MVP somente BRL** para totais consolidados; outras moedas exigem taxa histórica e regras próprias.
8. Se o deploy será exclusivamente local ou hospedado; em qualquer deploy remoto, validar a **única identidade proprietária** antes de acessar os dados.

**Defaults do MVP:** **single-user definitivo**, sem registro de usuários e sem recursos colaborativos; BRL, entrada manual, sem integração bancária, pagamentos registrados manualmente, sem cálculo de juros automático, ciclo de cartão configurável, alertas in-app e acesso restrito ao proprietário se publicado na web.

---

## 23. Instruções finais para o agente de desenvolvimento

Você é o arquiteto de software e engenheiro full-stack responsável por executar este projeto de forma incremental.

**Primeira resposta obrigatória, ANTES de criar arquivos/código:**

1. Leia integralmente este documento e inspecione o repositório existente.
2. Resuma o objetivo e identifique dependências e riscos de domínio financeiro.
3. Apresente a arquitetura das camadas, fronteiras entre os agregados e modelo de dados inicial.
4. Explique como impedir dupla contagem entre compra no cartão, pagamento de fatura, empréstimo, rateio e transferência.
5. Liste exatamente os arquivos que pretende criar/alterar na Etapa 1.
6. Especifique dependências, migrations, endpoints, testes e comandos de execução.
7. Identifique trade-offs; não adicione infraestrutura desnecessária, especialmente autenticação multiusuário, RBAC, convites, tenants, times ou workspaces.
8. **Aguarde aprovação explícita para implementar a Etapa 1.**

**Durante a implementação:**

- Trabalhe por etapas, sem construir tudo em uma só alteração.
- Evite lógica financeira em componentes React; backend é fonte de verdade.
- Prefira regras pequenas, puras, testáveis e documentadas.
- Nunca invente valores, métricas, dados bancários ou saldos para parecer que o sistema funciona.
- Antes de cada etapa, explique impacto no schema, risco de migração e testes.
- Ao final, forneça o que foi construído, como executar, testes rodados e limitações conhecidas.
- Não implemente acesso bancário automático, pagamento real ou notificações externas sem aprovação. **Não implemente compartilhamento, multiusuário ou SaaS; estão fora do escopo.**

**Resultado esperado:** um **painel de controle financeiro exclusivamente pessoal**, confiável, com dashboard detalhado, experiência profissional, rastreabilidade e evolução sustentável — não uma plataforma para outras pessoas nem um conjunto de telas bonitas com informações inconsistentes.
