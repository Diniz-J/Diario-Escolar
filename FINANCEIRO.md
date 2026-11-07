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

Dois comandos, os dois seguros de repetir:

**Quem dispara isso hoje** (out/2026): o workflow agendado
`.github/workflows/tarefas.yml`, que chama
`POST /api/v1/tarefas/executar/?tarefas=...`. Não é crontab no servidor
— o projeto não tinha cron em ambiente nenhum, e por isso estes três
commands existiam sem nunca rodar. O desenho da rota e o porquê do
Actions estão no item 12b do `CLAUDE.md`.

Os horários abaixo são os que o workflow usa. **Os minutos são quebrados
de propósito**: o GitHub atrasa workflow agendado que cai na virada da
hora, que é onde todo mundo agenda. A intenção é a mesma que o crontab
original registrava (dia 1 de manhã, emissão meia hora depois da
geração).

```cron
# Gera as faturas do mês, todo dia 1 — 03:11 em São Paulo.
11 6 1 * *   tarefas=faturas

# Emite no gateway o que a geração criou, meia hora depois.
41 6 1 * *   tarefas=cobrancas

# Move pra `vencido` o que venceu — diário, 04:11 em São Paulo.
# Junto vai o purge de token de redefinição expirado.
11 7 * * *   tarefas=vencidas,tokens
```

Num servidor com crontab próprio (fora do Render), as mesmas três linhas
viram `cd /app && python manage.py <command>` — o command é o mesmo, só o
agendador muda.

A emissão é **entrada separada**, e não parte da geração, porque
`gerar_faturas` roda numa transação e em lote: pendurar N chamadas HTTP
ali prenderia o lock das faturas pelo tempo do provedor, e uma falha no
meio desfaria as cobranças que já tinham sido criadas lá — que
continuariam existindo no Asaas sem fatura apontando pra elas. Também é
o que mantém o módulo funcionando sem gateway: sem a chave, a terceira
linha simplesmente não tem o que fazer.

`financeiro_gerar_faturas` aceita `--competencia YYYY-MM` (default: mês
corrente), `--escola <id>` e `--dry-run`. Rodar duas vezes no mesmo mês
não duplica nada: a segunda execução conta as faturas que já existem como
ignoradas. É o que permite re-rodar à mão depois de uma falha parcial.

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

### 2.8. Na virada de contrato, cobra o plano mais antigo do mês

Entre os planos ativos cuja vigência intersecta a competência, a geração
escolhe **o de `vigencia_inicio` mais antiga** — que é o que estava
valendo no dia 1 do mês.

O caso que obriga a ter regra: plano A encerra dia 10, plano B começa
dia 11. As duas vigências são legítimas e não se sobrepõem, as duas
passam na validação, e as duas cobrem março. Março sai pelo A, e o B
começa a cobrar em abril.

A mesma regra resolve matrícula nova no meio do mês: existe só o
contrato novo, então ele cobra o mês inteiro, valor cheio.

**Por que escolher na aplicação e não deixar o banco decidir**: a
alternativa seria tentar criar as duas faturas e deixar o unique de
`(aluno, competencia)` derrubar a segunda. Funcionaria, mas qual plano
cobra o mês passaria a depender da ordem de inserção — ou seja, o valor
no boleto do responsável seria arbitrário. A escolha é explícita e
determinística, e o comando avisa quando encontra um aluno nessa
situação.

**Rateio por dias está fora de escopo.** Seria o mais justo e o mais
caro: quebraria o invariante de uma fatura por aluno por mês e exigiria
campo de período na fatura. Se a escola pedir, é mudança de schema, não
ajuste de regra.

---

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

## 5. API

Rotas sob `/api/v1/`: `planos-cobranca/`, `faturas/`, `fatura-itens/` e
`pagamentos/`.

**Financeiro é só direção.** `IsAdminOrDiretor` uniforme em todas as
ações, leitura inclusive — pelos aliases do projeto cobre admin,
diretor, secretaria e coordenador. Professor e inspetor levam 403 em
tudo. Mensalidade, bolsa e inadimplência não são assunto de quem dá
aula, e é o mesmo raciocínio que já barra o professor no relatório
cadastral de alunos. A classe vai direto em `permission_classes`, sem o
`ReadWritePermissionMixin`: leitura e escrita têm a mesma regra, e como
o mixin sobrescreve `get_permissions`, deixá-lo no caminho faria
qualquer `permission_classes` de `@action` futura ser ignorada em
silêncio.

**O serializer roda o `clean()` do modelo, não uma cópia das regras.**
`materiais` e `aulas` reescrevem as invariantes dentro do `validate()`
(o DRF não chama `clean()`), o que é razoável quando a regra é uma
linha. O `PlanoCobranca` tem cinco, uma delas com consulta ao banco
(sobreposição de vigência) — duas cópias divergiriam, e divergência
aqui significa cobrança errada. `_validar_pelo_clean()` carrega uma
cópia rasa da instância com o payload e chama o `clean()` dela,
convertendo o erro do Django no do DRF com as chaves por campo
preservadas. Efeito colateral bom: em `PATCH` parcial as invariantes
enxergam o registro completo, não só o pedaço que veio no corpo.

**Quase tudo que mexe em dinheiro é read-only.** `status`, `valor_pago` e
`data_pagamento` da fatura são do `services.py` (fatia 3); `id_externo` e
`link_pagamento`, do gateway (fatia 4). `status` editável pela API seria
o caminho de marcar "pago" sem pagamento nenhum, e `id_externo` digitado
à mão é como se concilia a cobrança do aluno errado. `valor` e
`vencimento` seguem editáveis — a secretaria corrige fatura.

**`Fatura.aluno` é read-only e deduzido do `plano`.** O campo existe pra
sustentar o unique de `(aluno, competencia)` (§3.1), não pra ser
preenchido por quem chama. Consequência que exigiu código: o
`UniqueTogetherValidator` do DRF só monta a checagem quando todos os
campos do constraint são graváveis, então sem uma validação explícita a
competência repetida estouraria `IntegrityError` e o front mostraria
erro de servidor em vez de "este aluno já tem fatura neste mês".

**`DELETE` por recurso**: na fatura cancela (`status=cancelado`, e
recusa com 400 quando há pagamento registrado — estorne primeiro); no
plano desativa (`ativo=False`, o que também libera a vigência pra um
contrato novo); no item de fatura apaga de verdade, porque a linha é
detalhamento e corrigir taxa lançada errada é operação legítima da
secretaria — o audit log guarda o que saiu.

**`Pagamento` registra, lê e estorna, nunca edita.** `POST` e `DELETE`
delegam em `registrar_pagamento()`/`estornar_pagamento()`, que reconciliam
a fatura na mesma transação; o serializer de escrita não chama `save()`.
Não há `PUT`/`PATCH`: corrigir valor ou data de um pagamento já
conciliado deixaria a fatura com um número que não existe mais, então o
caminho é estornar e registrar de novo, que passa pelos dois lados da
conciliação. O `DELETE` é o que torna acionável a recusa de cancelar
fatura com pagamento registrado — estorna, depois cancela.

Detalhe que custou código: o DRF monta um `UniqueValidator` sozinho a
partir do `UniqueConstraint` de `referencia_externa`, e com ele o reenvio
do mesmo pagamento (duplo clique, retry de rede) morreria em 400 antes de
chegar ao service. O campo é declarado com `validators=[]` justamente pra
que a resposta venha de quem sabe dar a certa: o service devolve o
pagamento que já existe. O constraint continua no banco como rede.

Outro: o `services.py` valida com `full_clean()`, pra que as invariantes
valham para os três chamadores (API, command e webhook). O DRF não traduz
o `ValidationError` do Django, então a view converte no limite da API
(`erro_drf`) — sem isso, "fatura cancelada não recebe pagamento" sairia
como 500.

**Paginação**: `PaginacaoCompulsoria` em faturas e pagamentos (300
alunos por 12 meses são 3.600 linhas por ano letivo), `PaginacaoPadrao`
em planos e itens, que são listas curtas por aluno ou por fatura.

**`GET /financeiro/alunos/<id>/`** (fatia 6b) devolve a ficha do aluno:
totais mais os três históricos (contratos, faturas, pagamentos) numa
requisição, numa `APIView` sem modelo próprio — molde de `boletins` e
`relatorios`. Aluno de outra escola responde **404**, não 403: a
existência de aluno alheio não é informação que este endpoint deva
confirmar. (`boletins` responde 403 no mesmo caso; a divergência é
consciente, e o 404 é o que os viewsets deste módulo já produzem pelo
escopo do queryset.)

**Os totais são somados em Python, sobre os métodos do modelo, nunca em
SQL.** `Fatura.saldo()` trava em zero quando o pagamento foi a mais, e um
`Sum(F("valor") - F("valor_pago"))` faria o excesso de uma fatura abater
a dívida de outra — a ficha mostraria dívida menor que a real, e a escola
cobraria menos do que deve. Reusar os métodos também garante que a ficha
e a tela de faturas não discordem. O custo é carregar as faturas do aluno
em memória, recorte naturalmente pequeno (uma por mês por contrato). Só
`pago_no_ano` vem do banco, porque ali é soma simples de pagamentos, sem
piso nem regra. Teste que fixa isso:
`test_pagamento_a_mais_nao_abate_divida_de_outra_fatura`.

---

## 6. Integração com gateway

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

As envs do gateway (todas opcionais — sem elas o módulo opera sem
cobrança online):

| Env | Para quê |
|---|---|
| `ASAAS_API_KEY` | Autentica a **nossa saída** pra API deles. Sem ela, `gateway_configurado()` devolve `None` e a emissão recusa com mensagem. |
| `ASAAS_BASE_URL` | Sandbox (default) ou produção. Chave e ambiente andam juntos: cruzar os dois dá 401 `invalid_environment`. |
| `ASAAS_TIMEOUT` | Segundos (default 10). Curto porque a emissão acontece dentro de uma request da secretaria. |
| `ASAAS_WEBHOOK_TOKEN` | Valida a **entrada deles**. É o `authToken` do cadastro do hook no painel, **não** a API key — a doc deles diz isso explicitamente. Sem ela o endpoint recusa tudo. |

Decisões tomadas antes da fatia 4, e o que implementar provou:

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
  `GET /payments/{id}` antes de conciliar. O token prova quem mandou, não
  quanto entrou — `conciliar_cobranca` só lê o corpo pra achar a fatura.
- **Notificação ao responsável sai por `apps/portal/destinatarios.py`**,
  como ocorrência e comunicado. O pai vinculado só pelo M2M tem que
  receber — é a armadilha do `RESPONSAVEIS.md` §4.1. Mora em
  `apps/financeiro/notificacoes.py`, separada do `services.py`: lá é o que
  escreve dinheiro (não pode falhar em silêncio), aqui é melhor-esforço
  por definição.

Quatro coisas que só apareceram ao escrever o adaptador contra a
documentação deles, e que nenhum nome de campo revela:

- **`DELETE /payments/{id}` devolve `{deleted, id}`, não a cobrança.** O
  contrato promete uma `Cobranca`, então `cancelar_cobranca` apaga e
  relê. Consequência: se o `DELETE` passar e a releitura falhar, o
  adaptador levanta erro embora a cobrança esteja cancelada lá — por isso
  `services.cancelar_cobranca` trata falha como aviso, nunca como
  bloqueio. Cancelar fatura aqui não pode depender da disponibilidade
  deles.
- **`deleted` ganha do `status`.** Cobrança removida continua
  respondendo o status que tinha (`PENDING`, por exemplo). Ler só o
  status faria a conciliação tratar como viva uma cobrança que a escola
  já baixou.
- **O valor pago é `value`, não `netValue`.** `netValue` é o líquido
  depois da tarifa deles — usá-lo deixaria saldo residual em toda fatura.
  Quando o pagamento sai diferente do original (atraso com multa), é
  `originalValue` que guarda o original e `value` que traz o
  efetivamente pago; `value` é o certo nos dois casos.
- **`fine` tem `type`, `interest` não.** A multa vai como
  `{value, type: "PERCENTAGE"}` e os juros como `{value}` — mandar `type`
  nos juros faz o Asaas recusar. Os dois saem das cláusulas do
  `PlanoCobranca`, e vão **porque o encargo tem que estar no boleto**:
  sem isso o atraso é cobrado pelo valor de face e a escola teria que
  cobrar a diferença à mão.

O meio de pagamento que volta deles nem sempre cabe no nosso enum: a doc
diz que valor entrando na conta por Pix ou TED é associado a uma cobrança
existente, então a mensalidade emitida como "pagador escolhe" pode voltar
paga como `TRANSFER`/`DEPOSIT`. Daí `Pagamento.Metodo.OUTRO` — chutar
`boleto` gravaria fato errado numa tabela de dinheiro auditada. Não é
opção de secretaria: ela escolhe entre os quatro meios de sempre.

---

## 7. Frontend (fatia 6)

Duas telas sob um item só de sidebar, com abas internas
(`FinanceiroTabs`): `/financeiro` (faturas) e `/financeiro/planos`. O item
da sidebar some pra professor e inspetor — `podeVerFinanceiro` no
`usePermissoes`, espelhando o `IsAdminOrDiretor` uniforme do backend.
Flag com nome próprio em vez de reaproveitar `podeModificarCadastros`
porque aqui ela também decide **leitura**.

**Dinheiro chega como string.** O `DecimalField` do DRF serializa
`"1000.00"` pra não perder precisão em float, então os tipos do front
declaram `string` e `formatarBRL` só formata. Nenhuma aritmética de
dinheiro no front: saldo, encargos e valor atualizado vêm calculados do
backend, que é onde a regra mora.

**Datas sem hora não passam por `new Date`.** `new Date("2026-03-10")` é
lido como UTC e, em fuso negativo, volta como dia 9. `formatarData` e
`formatarCompetencia` fazem split da string. O mesmo cuidado no default
de data do pagamento: `toISOString()` à noite viraria amanhã, data
futura que o backend recusa.

**A mensagem de erro do backend é a UI.** Os dialogs mostram o texto que
vem do DRF em vez de um "erro ao salvar" genérico, porque é ali que as
invariantes se explicam: "Ana já tem fatura na competência 03/2026",
vigência sobreposta, "fatura cancelada não recebe pagamento". Está
centralizado em `features/financeiro/erros.ts`.

**Detalhe em dialog, não em rota.** Clicar na linha abre o detalhamento,
os pagamentos e os encargos do dia, com estorno por pagamento. Evita uma
segunda tela no padrão visual pra manter. O dialog de pagamento é aberto
pela **página**, não por dentro do de detalhe: dois dialogs abertos
brigam por foco e travam o scroll.

**"Nova fatura" existe de propósito**, mesmo com a geração automática
sendo a via normal: cobre o mês em que o cron ainda não rodou (ou não
está configurado — é o caso hoje, em ambiente nenhum) e a cobrança extra fora
do ciclo. O formulário sugere valor e vencimento a partir do plano, com
o mesmo clamp de mês curto, mas a régua que vale é a do backend.

Badges de status seguem o molde de ocorrência (`DESIGN.md` §6.1.1): é
estado de documento, não a paleta de presença.

**Ficha do aluno (fatia 6b)** em `/financeiro/alunos/:id`: quatro
contadores (em aberto, vencido, a cobrar hoje, pago no ano) sobre os três
históricos, reusando o `MetricCard` do dashboard. Os dialogs de
pagamento, detalhe e cancelamento são os mesmos da listagem, então a
ficha não é só leitura — vê a dívida e resolve ali.

Três entradas, de propósito, porque são três perguntas diferentes: o nome
do aluno na lista de faturas (quem já está olhando uma cobrança), o ⋯ da
`AlunosPage` (quem parte do cadastro) e o botão "Financeiro" na
`TurmaDetalhePage`, que leva pra `/financeiro?turma=<id>` — situação da
turma, não de um aluno. As três são de nível-diretor, como o endpoint.

---

## 8. Fatias

| # | Escopo | Status |
|---|---|---|
| 1 | Models, migration, admin, testes | **entregue** |
| 2 | API DRF (viewsets, serializers, filtros, permissões) | **entregue** |
| 3 | `services.py` + geração recorrente + job de vencidas | **entregue** |
| 4 | `gateways/base.py` + `asaas.py` + emissão | **entregue** |
| 5 | Webhook + conciliação + notificação ao responsável | **entregue** |
| 6 | Frontend — faturas e planos | **entregue** |
| 6b | Ficha financeira do aluno (endpoint + tela) | **entregue** |

A permissão ficou decidida na fatia 2: financeiro é **só direção**
(`IsAdminOrDiretor`, que já cobre secretaria e coordenador). Professor e
inspetor não leem mensalidade. Ver §5.

Fora de escopo até alguém pedir: nota fiscal de serviço, inadimplência
com régua de cobrança automática, split de pagamento, carnê impresso,
fatura no portal do responsável.

---

## 9. Estado

**Fatias 1, 2 e 3 entregues.** O módulo está funcional ponta a ponta sem
gateway: os quatro modelos, a API REST sob `/api/v1/`, e o `services.py`
com geração recorrente idempotente, conciliação (registro e estorno) e o
job de vencidas, com dois management commands pra cron. 150 testes.

Uma escola já pode operar assim: cadastra o plano de cada aluno, o cron
gera as faturas todo dia 1, a secretaria registra o Pix ou o dinheiro que
recebeu e o status acompanha. O que falta é a cobrança sair
automaticamente (fatias 4 e 5) e a tela (fatia 6).

**Fatias 6 e 6b entregues**: a escola opera o módulo inteiro pela UI,
sem passar pelo `/admin/`, e a ficha do aluno responde "quanto este aluno
deve" com os totais somados no servidor.

**Fatias 4 e 5 entregues**, e com elas o módulo fecha: a escola emite a
cobrança (`POST /faturas/<id>/emitir-cobranca/` na tela, ou
`financeiro_emitir_cobrancas` no cron), a família paga pelo link do
provedor e o webhook concilia e avisa o responsável, sem ninguém abrir o
sistema.

O que a fatia 4 trouxe de schema, porque a emissão exigia: `pagador` no
`PlanoCobranca` (FK pro `Responsavel`) e `id_externo_gateway` no
`Responsavel`. O pagador mora no **contrato**, não no aluno, porque o
aluno com mãe e pai vinculados tem dois responsáveis no portal e um só
titular de boleto — deixar a escolha implícita ("o primeiro com CPF")
faria o titular trocar sozinho no dia em que alguém preenchesse o CPF do
outro. O `clean()` exige que o pagador seja responsável **daquele**
aluno: cobrar em nome de quem não tem vínculo poria um terceiro no boleto
da família. O `id_externo_gateway` existe porque criar cliente no Asaas
**não** é idempotente — sem guardar o id, cada emissão abriria outro
cadastro e espalharia o histórico da mesma família por vários clientes.

O que falta pra operar de verdade não é código: as **entradas de cron**
(§2.2) e as quatro envs (§6) precisam ser configuradas no servidor, e o
hook tem que ser cadastrado no painel do Asaas apontando pra
`/api/v1/financeiro/webhooks/asaas/` com o mesmo `authToken` que entrar
em `ASAAS_WEBHOOK_TOKEN`.
