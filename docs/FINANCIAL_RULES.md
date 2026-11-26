# Regras financeiras

## Dinheiro

- Todo valor é inteiro em **centavos** (`BIGINT`), sufixo `_cents` na API. Nunca `float`.
- Entrada de usuário (`"1.234,56"`) é convertida para centavos por parse de string, sem ponto flutuante.
- Divisão em N partes: `base = total // N`, resto distribuído com +1 centavo nas primeiras partes (100,00/3 = 33,34 + 33,33 + 33,33).

## Livro de caixa (`transactions`)

`amount_cents` é **assinado**: positivo entra, negativo sai. `kind` define a natureza:

| kind | Sinal | Conta como receita/despesa? |
|---|---|---|
| `INCOME` | + | receita |
| `EXPENSE` | − | despesa (categorizada) |
| `TRANSFER_OUT` / `TRANSFER_IN` | − / + | **não** (movimento interno) |
| `ADJUSTMENT` | ± | **não** (conciliação) |
| `CARD_PAYMENT` (Etapa 2) | − | **não** (o consumo já foi contado na compra) |
| `LOAN_OUT` / `LOAN_IN` (Etapa 4) | − / + | **não** |
| `SETTLEMENT_IN` / `SETTLEMENT_OUT` (Etapas 3–4) | + / − | **não** |

Relatórios de receita/despesa filtram **por `kind`**, nunca pelo sinal do valor.

## Status

- `POSTED` (efetivado) altera saldo atual.
- `PLANNED` (previsto) **não** altera saldo; entra só em projeções.
- `CANCELLED` não altera nada e é mantido para histórico.

## Saldo

`saldo_atual(conta) = opening_balance_cents + Σ amount_cents (status = POSTED)`.
Conta arquivada não aceita novos lançamentos.

## Transferência

Uma transação de banco cria duas pernas com o mesmo `transfer_group_id`: `TRANSFER_OUT` (−v) na origem e `TRANSFER_IN` (+v) na destino. A soma dos saldos é preservada. Origem ≠ destino, valor > 0.

## Idempotência

Operações de escrita financeira aceitam `idempotency_key`. Mesma chave com o mesmo payload devolve o registro original; mesma chave com payload diferente devolve **409**. A chave é única no banco (constraint) e o hash do payload é guardado.

## Correções

Um lançamento efetivado não é apagado: é cancelado (status `CANCELLED`) com registro em `audit_events`. Ajuste de conciliação gera `ADJUSTMENT`, e o saldo inicial nunca é alterado silenciosamente.

## Regimes

- Saldos e fluxo: **caixa** (por `effective_date`).
- Consumo por categoria: **competência** (a partir da Etapa 2, compras no cartão entram pela competência da parcela).

## Cartão: ciclos, parcelas e vencimento

- Ciclo da compra: `[fechamento anterior, fechamento)`; compra no dia do fechamento segue a política do cartão
  (`EXCLUSIVE` → próxima fatura, `INCLUSIVE` → fatura atual).
- **Uma parcela por fatura**: a parcela N vai para o ciclo N−1 meses após o da compra (faturas encadeadas,
  sem buraco). Até 2026-11 todas as parcelas iam para a 1ª fatura — corrigido com teste de regressão.
- **Vencimento conta a partir do fechamento** (`cycle_end_exclusive`): `due_month_offset = 1` → dia `due_day` do
  mês seguinte ao fechamento (fecha 10/12, vence 05/01); `0` → mesmo mês, exigindo `due_day > closing_day`
  (senão a API recusa com `due_before_closing`). A fatura nunca vence antes de fechar.

## Dupla contagem — matriz

| Evento | Caixa | Consumo |
|---|---|---|
| Compra no cartão | — | parcelas na competência |
| Pagamento de fatura | `CARD_PAYMENT` | — |
| Transferência | 2 pernas | — |
| Empréstimo concedido | `LOAN_OUT` + recebível | — |
| Rateio | 1 despesa + recebíveis das partes alheias | despesa bruta uma vez |
| Reembolso recebido | `SETTLEMENT_IN` | — (custo líquido só em relatório) |
