# FINANCEIRO.md — Cobrança de mensalidade

Desenho do módulo financeiro: **contas a receber** da mensalidade
escolar, com conciliação por webhook de um gateway brasileiro.

Leia junto com o `CLAUDE.md` (guardrails do repositório e mapa do código)
e o [`RESPONSAVEIS.md`](./RESPONSAVEIS.md) (quem recebe email — vale pro
aviso de fatura também).

---

## 1. Fronteira do módulo

**A emissão de boleto/Pix não é nossa.** Emitir cobrança no Brasil exige
convênio bancário, registro de boleto na CIP, chave Pix, e a conta-corrente
da escola. Isso é trabalho de gateway (Asaas), não de ERP escolar.

O que é nosso:

| Nosso | Do gateway |
|---|---|
| Contrato financeiro do aluno (valor, vencimento, desconto, vigência) | Emissão do boleto / QR Pix |
| Geração das faturas por competência | Link de pagamento |
| Contas a receber (quem deve o quê, desde quando) | Confirmação do pagamento |
| Conciliação (o que entrou bate com qual fatura) | Repasse pra conta da escola |
| Multa e juros como regra | Cálculo de taxas do gateway |

Por isso a `Fatura` guarda `id_externo` e `link_pagamento`: são o ponteiro
pra cobrança lá e o link que o responsável abre. Nada mais do gateway
entra no nosso schema.

**Consequência de arquitetura**: o contas a receber funciona sem gateway
nenhum. A escola que recebe Pix na conta e dinheiro na secretaria usa o
módulo registrando `Pagamento` manual. O gateway é integração, não
dependência.

---

## 2. Decisões tomadas

### 2.1. A recorrência é nossa, não do gateway

Asaas e Vindi têm assinatura nativa: você cria uma `subscription` e eles
emitem as cobranças mensais. **Não usamos.**

Motivo: bolsa e desconto variável, competência, reemissão e cancelamento
são regra da escola, e a escola muda de regra. Com a recorrência no
gateway, cada mudança dessas vira chamada de API — e o histórico
financeiro passa a morar lá, o que transforma "trocar de provedor" em
migração de dados em vez de troca de adapter.

Com a recorrência nossa, o gateway recebe **cobrança avulsa por fatura**.
Trocar Asaas por outro é reescrever um arquivo.

### 2.2. Geração por management command, não Celery

O projeto não tem fila (`CLAUDE.md` FASE 4, item 12 — pendente). O
assíncrono hoje é thread daemon (`ocorrencias`, `comunicados`) mais
command idempotente de retomada (`comunicados_retomar`). A geração mensal
segue o mesmo caminho: command + cron, idempotente pelo unique de banco.

Quando a fila existir, a geração migra sem mudar o modelo — o que garante
a idempotência é a constraint, não o agendador.

### 2.3. Multa e juros são regra, não campo

`Fatura.encargos(hoje)` calcula multa + juros de mora pro rata die a
partir dos percentuais do plano. Gravar o encargo congelaria um número
que muda todo dia; o que é estável é a regra.

Os percentuais ficam no `PlanoCobranca` (não em settings) porque são
**cláusula de contrato**: o default vem da env no momento do cadastro e
depois pertence ao plano. Reajustar a env não reescreve contrato assinado.

Juros ao mês viram juros ao dia por `/30` — prática corrente de cobrança
no Brasil (1% ao mês = 1/30% por dia), não pela quantidade de dias do mês
real.

### 2.4. `valor_pago` e `status` são escritos pelo service, nunca pelo `save()`

Tentador: `Pagamento.save()` soma no `valor_pago` da fatura e move o
status. Recusado por dois motivos — quebra em `bulk_create`/`bulk_update`
(que não chamam `save()`), e esconde o momento em que o dinheiro muda o
estado da fatura, que é exatamente o que precisa ficar rastreável num
módulo de dinheiro.

Há teste travando isso (`test_salvar_pagamento_nao_toca_na_fatura`): se
alguém mover a conciliação pro `save()`, o teste cai e a decisão volta pra
mesa em vez de mudar em silêncio.

### 2.5. Dinheiro em `DecimalField`, sempre

Todo campo monetário é `DecimalField(max_digits=10, decimal_places=2)`.
Nunca `FloatField` — `0.1 + 0.2 != 0.3` em binário, e o erro aparece na
soma do mês.

Arredondamento é **comercial** (`ROUND_HALF_UP`), não o
`ROUND_HALF_EVEN` default do `Decimal`: em boleto de escola a expectativa
é que 0,005 suba. Centralizado em `arredondar_dinheiro()`.

### 2.6. `competencia` é `DateField` travado no dia 1

Em vez de um par `mes`/`ano`: ordenação, range (`?de=&ate=`) e unique
saem de graça, e "março de 2026" é uma data, não dois inteiros. O dia 1 é
imposto no `clean()`.

### 2.7. `dia_vencimento` aceita 1 a 31

O dia 31 é cadastro legítimo ("vence no último dia"). Quem resolve
fevereiro é o clamp da geração, que trava no último dia do mês da
competência. Validar em 1..28 obrigaria a escola a mentir no cadastro.

---

## 3. Invariantes

### 3.1. Uma mensalidade por aluno por mês

**É o invariante central do módulo.** `Fatura` tem unique de banco em
`(aluno, competencia)`.

O caminho óbvio seria `(plano, competencia)` — e ele tem um buraco. Troca
de plano no meio do mês é cadastro legítimo: o plano A encerra dia 10, o
plano B começa dia 11, as vigências não se sobrepõem e as duas passam na
validação. Com unique por plano, a geração mensal criaria **duas faturas
de março** e o aluno seria cobrado duas vezes no mês da virada.

Constraint de banco não atravessa FK, então `Fatura.aluno` é
desnormalizado do plano — essa é a única razão do campo existir. O
`clean()` trava `fatura.aluno == plano.aluno` pra desnormalização não
poder divergir.

Teste: `test_troca_de_plano_no_meio_do_mes_nao_cobra_duas_vezes`.

### 3.2. Vigência sobreposta é barrada na aplicação — e isso é limitação conhecida

`PlanoCobranca.clean()` recusa dois planos **ativos** do mesmo aluno com
vigência sobreposta (intervalos fechados, `vigencia_fim=None` valendo
infinito). Desativar o plano antigo libera a vigência pro novo.

**Limitação conhecida, aceita na v1**: a checagem é de aplicação, não de
banco.

- `objects.create()` e `bulk_create()` não chamam `clean()`.
- Duas requisições concorrentes podem passar as duas (não há lock entre
  o `SELECT` da checagem e o `INSERT`).

Aceitável porque o estrago que ela evitaria já é barrado no destino: o
unique de `(aluno, competencia)` impede a cobrança dupla mesmo com dois
planos sobrepostos no banco. O que se perde é a clareza do cadastro, não
o dinheiro do responsável.

**Caminho pra garantia de banco, quando valer o custo**: exclusion
constraint em `daterange`, que é o jeito nativo do Postgres de dizer "estes
intervalos não podem se sobrepor":

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE financeiro_planocobranca
  ADD CONSTRAINT plano_cob_vigencia_sem_sobreposicao
  EXCLUDE USING gist (
    aluno_id WITH =,
    daterange(vigencia_inicio, vigencia_fim, '[]') WITH &&
  ) WHERE (ativo);
```

Em Django: `django.contrib.postgres.constraints.ExclusionConstraint` com
`RangeOperators.OVERLAPS`, mais uma migration que habilite `btree_gist`
(`BtreeGistExtension`). Custo: a extensão precisa existir no banco
gerenciado (no Render e na OVH existe), e `ExclusionConstraint` exige
`django.contrib.postgres` no `INSTALLED_APPS` — que o projeto hoje não
usa. Por isso ficou anotado em vez de feito.

### 3.3. Escopo de escola

Os quatro modelos herdam `BaseModelEscopado`. `clean()` valida escola
alinhada em cada FK (aluno↔plano, plano↔fatura, fatura↔item,
fatura↔pagamento). A API (fatia 2) acrescenta `EscopoEscolaMixin` na
leitura e `validate_escola_do_usuario` na escrita, como todo o resto do
projeto.

### 3.4. Idempotência da conciliação

Dois uniques parciais (só quando o campo não está vazio, porque vazio é o
estado normal de quem nunca foi pro gateway):

- `Fatura.id_externo` — duas faturas apontando pra mesma cobrança fariam
  o webhook conciliar a errada.
- `Pagamento.referencia_externa` — o Asaas **reentrega o mesmo evento**
  por design; sem o unique, cada reentrega viraria um pagamento novo.

### 3.5. `FaturaItem` é detalhamento, não fonte da verdade

`Fatura.valor` é o quanto cobrar. O item explica a composição
(mensalidade + taxa + material) pro responsável. A igualdade entre a soma
das linhas e o valor da fatura é responsabilidade de quem monta as duas
coisas (`services.py`), **não** uma invariante de banco: travá-la no
`clean()` faria a ordem dos saves importar, e qualquer item salvo antes do
ajuste do total cairia num erro sem culpa.

`FaturaItem.fatura` é `CASCADE` — mesma exceção do `ItemPresenca`: o ciclo
de vida da linha pertence ao documento, e item órfão não significa nada. É
a única exceção de `PROTECT` que o módulo abre.

---

## 4. Modelo de dados

```
Aluno ──< PlanoCobranca ──< Fatura ──< FaturaItem   (CASCADE)
            (contrato)      │  └─────< Pagamento    (PROTECT)
                            │
            unique(aluno, competencia) ◄── o invariante central
```

- **`PlanoCobranca`** — `aluno`, `valor_mensalidade`, `dia_vencimento`,
  `desconto_tipo` (nenhum/percentual/fixo) + `desconto_valor`,
  `multa_percentual`, `juros_mes_percentual`, `vigencia_inicio`,
  `vigencia_fim`, `ativo`. Métodos: `valor_efetivo()`, `vigente_em()`,
  `plano_sobreposto()`.
- **`Fatura`** — `plano`, `aluno`, `competencia`, `valor` (congelado na
  geração), `vencimento`, `status`
  (pendente/pago/vencido/cancelado), `valor_pago`, `data_pagamento`,
  `id_externo`, `link_pagamento`. Métodos: `saldo()`, `dias_atraso()`,
  `encargos()`, `valor_atualizado()`, `esta_vencida()`.
- **`FaturaItem`** — `fatura`, `descricao`, `valor`.
- **`Pagamento`** — `fatura`, `valor`, `data`, `metodo`
  (pix/boleto/cartao/dinheiro), `referencia_externa`.

Os quatro são auditados (`HistoricalRecords`) — é dinheiro, todo toque
precisa de autor e diff.

**Por que `valor` é congelado na fatura** e não lido do plano na hora de
exibir: reajuste em maio não pode reescrever a fatura de março, que já foi
enviada ao responsável.

---

## 5. Integração com gateway

Client isolado atrás de interface:

```
apps/financeiro/gateways/
  base.py    — GatewayPagamento (interface)
  asaas.py   — implementação Asaas (httpx)
```

Fluxo: gera `Fatura` → cria cobrança no gateway → guarda `id_externo` +
`link_pagamento` na fatura → webhook de pagamento confirmado → acha a
fatura pelo `id_externo` → `services.registrar_pagamento()` → notifica o
responsável.

Decisões já tomadas pra quando a fatia 4 começar:

- **Gateway: Asaas.** Boleto + Pix + cartão, API e webhook decentes, taxa
  baixa, popular em escola e clínica. Vindi é alternativa, mais forte em
  assinatura pura — que não usamos (§2.1).
- **Client próprio, fino, em `httpx`.** Não existe SDK Python maduro do
  Asaas (os que existem têm ≤3 estrelas); a maturidade do ecossistema
  deles está no PHP. Os não-oficiais servem de referência, não de
  dependência.
- **Dois tokens diferentes, não confundir**: o header `access_token` é o
  nosso, nas chamadas de saída pra API deles; o header
  `asaas-access-token` é o que **eles** mandam no webhook, com o valor que
  configuramos no cadastro do hook. Validar o segundo em comparação
  constant-time antes de confiar em qualquer coisa do corpo.
- **Webhook idempotente pelo id do evento**, com modelo próprio
  (`unique` no id) — reentrega é comportamento normal do Asaas, não erro.
- **Não confiar no corpo do webhook pra valor**: reconsultar
  `GET /payments/{id}` antes de conciliar.
- **Notificação ao responsável sai por `apps/portal/destinatarios.py`**,
  como ocorrência e comunicado. O pai vinculado só pelo M2M tem que
  receber — é a armadilha do `RESPONSAVEIS.md` §4.1.

---

## 6. Fatias

| # | Escopo | Status |
|---|---|---|
| 1 | Models, migration, admin, testes | **entregue** |
| 2 | API DRF (viewsets, serializers, filtros, permissões) | pendente |
| 3 | `services.py` + geração recorrente + job de vencidas | pendente |
| 4 | `gateways/base.py` + `asaas.py` | pendente |
| 5 | Webhook + conciliação + notificação ao responsável | pendente |
| 6 | Frontend (ficha financeira, listagem da secretaria) | pendente |

Decisão de permissão pendente de confirmação na fatia 2: financeiro é
**só direção** (`IsAdminOrDiretor`, que já cobre secretaria e
coordenador). Professor e inspetor não leem mensalidade.

Fora de escopo até alguém pedir: nota fiscal de serviço, inadimplência
com régua de cobrança automática, split de pagamento, carnê impresso,
fatura no portal do responsável.

---

## 7. Estado

**Fatia 1 entregue.** App `financeiro` com os quatro modelos, escopo por
escola, audit log, admin com inlines na fatura e 60 testes. Nenhuma rota
exposta ainda — o cadastro é pelo `/admin/`.
