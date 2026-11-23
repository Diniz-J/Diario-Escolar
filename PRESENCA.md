# PRESENCA.md — Presença por tempo de aula + grade horária

Desenho da migração da presença **diária** para presença **por tempo de
aula**, com grade horária por turma. Decidido em nov/2026.

---

## 1. O que mudou

**Entregue em nov/2026** (PRs #179 a #183; §6 tem as fatias e o que o
code review pegou). Este documento é o registro das decisões, não um
plano — o que ele descreve está no ar.

Até então a chamada era uma por `(escola, turma, data)` e a frequência
contava **itens**: o denominador era "dias com chamada". Passou a ser uma
chamada por **bloco de tempos** de uma turma num dia, e a frequência soma
**tempos** — o denominador é carga horária, que é a régua da LDB (75% da
carga, não dos dias).

Três coisas entraram juntas: o bloco de tempos no registro, o professor
resolvido do usuário logado, e a grade horária que pré-preenche os
tempos do dia.

---

## 2. Decisões travadas

**2.1 A grade sugere; o registro é dono do dado.** A chamada copia tempo,
disciplina e professor da grade — não aponta por FK pra linha dela.
Mesma razão do valor congelado da `Fatura`: editar a grade (ou realocar
em janeiro) não pode reescrever chamada passada. De quebra, professor
cobrindo falta de colega, reposição e sábado letivo deixam de ser
exceção de schema e passam a ser edição normal.

**2.2 Uma chamada vale N tempos, com peso uniforme.** Dois tempos
seguidos são um registro com `tempos=[1,2]`, não dois registros. O
objetivo é o professor clicar uma vez. Quem quiser granularidade
intra-bloco abre duas chamadas de um tempo cada — o modelo permite, só
não é o default.

**2.3 O `R` (retardatário) é crachá, não peso.** Continua contando como
presença efetiva, como hoje. A política ("5 atrasos viram 1 falta",
"atraso desconta o primeiro tempo") fica para quando a escola decidir —
e **não exige schema**: o `R` já é gravado com data, turma e os tempos
do bloco, então a regra futura é peso no serviço de cálculo.

Armadilha registrada: se um dia o `R` passar a descontar tempo, o
desconto é no máximo `len(tempos) - 1`. Num bloco de um tempo só, o
desconto integral faria o atrasado virar ausente — hoje ele conta
presente, e não é isso que se quer mudar.

**2.4 Frequência global é a oficial; por disciplina é informativa.** O
percentual que vale pro conselho e pro corte de 75% soma todos os
tempos. A quebra por disciplina existe só nos registros que têm
disciplina (ver 2.5).

**2.5 `disciplina` é opcional no registro.** Nulo significa "chamada do
dia", não de uma aula. É o que faz o mesmo modelo servir fundamental I
(professor polivalente, dia todo, sem disciplina) e ensino médio (por
tempo e por matéria) — requisito de whitelabel. Os dois modos ficam
sempre disponíveis na tela; nada de flag por escola, porque a mesma
escola pode ter os dois segmentos em turnos diferentes.

**2.6 O slot da grade aponta pro `Lecionamento`.** O vínculo
professor × turma × disciplina já existe e é validado, então a grade
herda a validação e não há como montar slot com trio inválido. Custo
aceito: os lecionamentos têm que existir antes de montar a grade, e não
há slot "a definir".

**2.7 A grade é a única verdade sobre dias de aula.**
`Lecionamento.dias_semana` é removido (fatia 5) — a grade diz dia **e**
tempo, é estritamente mais informação, e duas fontes sobre o mesmo fato
divergiriam. `aulas.services.projetar_agenda` passa a ler os dias
distintos da grade.

**2.8 O diário de aula (`RegistroAula`) continua por dia.** Unique
`(escola, turma, disciplina, data)` intacto. O que importa no diário é o
conteúdo que o professor deu no dia, não em que tempo deu — mesmo quando
dá três tempos em dois blocos. Assimetria consciente: presença por
tempo, diário por dia.

**2.9 O registro guarda ordinal, não horário.** `tempos` é um array de
ordinais (`[1, 2]`), e o horário sai do catálogo na hora de exibir. Um
array de pares de hora no registro não se paga. Consequência aceita:
reimprimir diário de março depois de a escola mexer nos horários mostra
o horário novo ao lado do tempo correto.

**2.10 Sobreposição de tempos é barrada no `clean()`, não no banco.**
`ArrayField` permite manter a frequência numa query só
(`array_length` como peso), e isso importa porque o relatório de
frequência por turma tem `assertNumQueries` travando query única. O
preço é a mesma limitação da vigência sobreposta do `PlanoCobranca`
(`FINANCEIRO.md` §3.2): duas requisições simultâneas podem criar
sobreposição. Risco baixo — é um professor abrindo a chamada, não um
processo concorrente. Caminho se virar problema: tabela filha
`RegistroPresencaTempo` com unique `(escola, turma, data, ordem)`, ao
custo de um join na agregação.

---

## 3. Schema

### 3.1 `TempoAula` (novo) — catálogo de horários da escola

| campo | tipo | nota |
|---|---|---|
| `escola` | FK PROTECT | `BaseModelEscopado` |
| `turno` | choices de `Turma.Turno` | matutino/vespertino/noturno/integral |
| `ordem` | PositiveSmallInteger | 1, 2, 3… |
| `hora_inicio` / `hora_fim` | TimeField | |
| `ativo` | Boolean | soft delete |

Unique `(escola, turno, ordem)`. É o que torna a duração do tempo
configurável por cliente — nada de 50 minutos no código.

### 3.2 `AulaGrade` (novo) — o slot da grade

| campo | tipo | nota |
|---|---|---|
| `escola` | FK PROTECT | |
| `lecionamento` | FK CASCADE | dá turma, disciplina e professor validados |
| `turma` | FK PROTECT | **desnormalizado** — ver abaixo |
| `dia_semana` | `Lecionamento.DiaSemana` | 0=segunda, alinhado a `date.weekday()` |
| `tempo` | FK `TempoAula` PROTECT | |
| `ativo` | Boolean | |

Unique `(escola, turma, dia_semana, tempo)`.

**`turma` é desnormalizado e essa é a única razão do campo.** A garantia
que importa é "um tempo da turma num dia não tem dois slots", e
`UniqueConstraint` não atravessa FK — sem a cópia, a garantia cairia pro
`clean()`. Mesmo caso e mesma justificativa de `Fatura.aluno`
(`FINANCEIRO.md` §3). `ano_letivo` segue derivado da turma, como no
`Lecionamento`.

`clean()`: `lecionamento.turma == turma`, escola alinhada nos três,
`tempo.turno == turma.turno`.

### 3.3 `RegistroPresenca` (alterado)

| mudança | nota |
|---|---|
| `+ tempos` | `ArrayField(PositiveSmallIntegerField)`, ordinais cobertos; obrigatório, não-vazio |
| `+ disciplina` | FK PROTECT, **opcional** (nulo = chamada do dia) |
| `professor` | resolvido do usuário logado no `perform_create`; direção pode lançar por outro |
| `- unique (escola, turma, data)` | cai — a turma passa a ter N chamadas por dia |
| migração | `AddField` com default `tempo_unico` já grava `[1]` nas linhas existentes — não precisou de data migration |

**O default do campo é `[1]`, não lista vazia, e isso não é cosmética.**
O peso de um item na frequência é o tamanho do bloco, então bloco vazio
faria o registro desaparecer do denominador **em silêncio**. Com `[1]`,
qualquer chamada criada fora da API (shell, management command, migration)
tem exatamente a semântica que a chamada diária tinha. A função é nomeada
(`tempo_unico`) porque default de `ArrayField` precisa ser serializável
pela migration.

**`tempos` é opcional no payload e, omitido, cobre o dia todo** — o turno
inteiro da turma (`tempos_padrao`), ou um tempo onde não há catálogo. É o
que mantém o cliente que ainda não manda o campo (a tela de chamada, até
a fatia 4) funcionando com a mesma semântica de antes: uma chamada por
dia, valendo o dia.

**Os ordinais só são validados contra o catálogo quando ele existe.** A
escola que ainda não cadastrou `TempoAula` nenhum continua lançando
chamada — é o estado de toda instalação antes de a grade ser montada, o
banco de demo inclusive. Exigir o catálogo aqui travaria a chamada por
causa de um cadastro que ninguém pediu ainda.

**O professor deixou de vir de um select: quem lança assina.** A view o
resolve do usuário logado, no molde do `RegistroAula`. A direção segue
podendo lançar por outro (é ela que cobre falta e corrige lançamento), e
o professor que tenta lançar em nome de outro leva 403 em vez de ter o
campo sobrescrito em silêncio. Inspetor opera como professor mas não tem
cadastro de `Professor`: a chamada dele fica sem assinatura, como antes.

`clean()`: tempos existem no catálogo do turno da turma; tempos não
sobrepõem outra chamada da mesma turma no mesmo dia.

### 3.4 `ItemPresenca` — intocado

Status continua `P`/`A`/`J`/`R`, unique `(registro, aluno)`, `CASCADE`
no pai, auto-geração por aluno ativo. É o que mantém timeline, portal e
boletim funcionando sem reescrita.

---

## 4. Régua de frequência

| status | peso |
|---|---|
| `P` | `len(tempos)` |
| `J` | `len(tempos)` |
| `R` | `len(tempos)` (ver 2.3) |
| `A` | 0 |

Denominador: soma dos `len(tempos)` das chamadas em que o aluno tem
item. Deixa de ser `COUNT(itens)` e passa a ser soma ponderada — os três
lugares que calculam isso mudaram juntos, na mesma PR.

O peso sai do lookup `len` do `ArrayField`
(`registro__tempos__len`, que o Postgres resolve como
`coalesce(array_length(tempos, 1), 0)`), dentro de
`Coalesce(Sum(..., filter=...), 0)`. Isso é o que mantém o relatório por
turma em **duas queries fixas** independentes do tamanho da turma — tem
`assertNumQueries` travando, e é a razão de o peso não ser resolvido em
Python. O `Coalesce` externo existe porque `Sum` sobre `LEFT JOIN` sem
linha devolve `NULL`, e o aluno sem chamada na janela tem que aparecer
com zero.

Os três lugares:

- `apps/boletins/services.py::calcular_frequencia`
- `apps/relatorios/services.py` — frequência por turma (atenção ao
  `assertNumQueries`) e presença média do dashboard
- `_STATUS_EFETIVOS` **continua** sendo lista de status: como o `R` é
  crachá (§2.3), o peso é uniforme e o que mudou foi a unidade somada,
  não a régua de quem conta como presente

O relatório ganhou `total_chamadas_aluno` ao lado do total em tempos, e os
cabeçalhos do CSV/XLSX passaram a dizer `_aulas`: "faltas: 4" num dia de
bloco duplo seria lido pela secretaria como quatro dias de ausência.

**Armadilha do teste:** até nov/2026 toda chamada valia 1, então contar
itens e somar tempos davam o mesmo número — a suíte inteira passou sem
mudança nenhuma depois do refactor. Todo teste da régua nova usa bloco de
tamanho **diferente de 1** (`apps/relatorios/tests/test_frequencia_ponderada.py`);
sem isso o teste passa pelo motivo errado e não impede ninguém de voltar
a contar chamadas.

O teste de não-divergência boletim × relatório continua sendo o que
impede as duas pontas de se afastarem.

**Timeline não muda de régua**: `A`, `J` e `R` seguem entrando como
evento e `P` seguindo fora, pelo motivo já registrado no `CLAUDE.md` —
lá a pergunta é "o que aconteceu", não "quantas faltas tem".

---

## 5. Fora de escopo (de propósito)

- **Peso do atraso** — ver 2.3. Não exige schema quando entrar.
- **Saída antecipada** — sair cedo é combinado com a escola e já tem
  aviso próprio. Não vale um quinto botão na linha do aluno.
- **Diário de aula por tempo** — ver 2.8.
- **Horário congelado no registro** — ver 2.9.

---

## 6. Fatias (uma PR cada)

| # | Fatia | Entrega |
|---|---|---|
| 1 | Grade — backend | **entregue** — este doc, `TempoAula`, `AulaGrade`, migration, admin, API só-direção |
| 2 | Grade — frontend | **entregue** — `/grade` (matriz da turma) e `/grade/tempos` (catálogo), mais a action `clonar` que a tela consome |
| 3 | Presença por tempo | **entregue** — §3.3 mais a régua da §4, na mesma PR |
| 4 | Tela de chamada | **entregue** — tempos pré-marcados pela grade, modo dia-todo, ajuste manual, e o bloco visível na listagem e no detalhe |
| 5 | Aposentar `dias_semana` | **entregue** — `projetar_agenda` lê a grade, campo removido, e o serializer expõe `dias_grade` derivado |

Ordem: grade antes da presença, pra a tela de chamada (fatia 4) nascer
já com a sugestão e não ser reescrita.

**As cinco fatias estão mergeadas** (PRs #179 a #183, nov/2026), e a
`main` ficou verde depois da #184.

### 6.1 O que o code review pegou

Cada fatia levou um commit de conserto antes do merge, e os cinco apontam
para o mesmo tipo de erro: a invariante foi aplicada **num caminho só**.
Ficam aqui porque a próxima pessoa a mexer nisto vai passar pelos mesmos
pontos.

**A invariante do `create` não vale no `update`.** `perform_create`
resolvia o professor do usuário logado, mas o PATCH ficou aberto: um
professor podia assinar por cima da chamada alheia, ou esticar `tempos`
num registro antigo — e esticar o bloco **reescreve o peso da
frequência** retroativamente, sem nada na UI dizendo que o percentual do
boletim mudou. O `perform_update` trava os dois campos fora da direção.

**Remover coluna sem migrar o dado esvazia a tela em silêncio.** A fatia
5 derrubou `Lecionamento.dias_semana` depois de a projeção passar a ler a
grade, mas quem tinha dias preenchidos e nenhum slot ficaria sem agenda
no diário — e nada falharia. A `escola/0011` ganhou `RunPython`
idempotente que cria um slot no primeiro `TempoAula` ativo do turno. O
agravante: a fatia 3 fez exatamente esse cuidado para `tempos` (§3.3), e
a 5 não o repetiu.

**`PROTECT` não protege soft delete.** O comentário original dizia "tempo
em uso por slot da grade é `PROTECT`" — falso: o FK só dispara em delete
hard, e ali o `DELETE` desativa. Desativar tempo ainda referenciado por
slot ativo deixava a grade apontando pra horário morto. Comentário que
afirma garantia inexistente é pior que comentário nenhum.

**Filtrar o slot não é filtrar o vínculo.** `projetar_agenda` exigia
`AulaGrade.ativo` mas não `lecionamento__ativo`, então slot ativo
pendurado em vínculo encerrado seguia projetando aula de professor que
saiu.

**Check-then-insert sem lock é 500 sob concorrência.** O clone validava
"destino sem grade" fora da transação do `bulk_create`: dois POSTs
simultâneos passavam os dois e o segundo morria no unique parcial. Virou
transação com `select_for_update` na turma destino, com o
`IntegrityError` restante traduzido pra 400. O mapa de
`(professor, disciplina)` também passou a resolver empate pelo menor id,
porque o modelo não impede dois lecionamentos ativos do mesmo par.

**Estado derivado precisa resetar quando o contexto muda.** No dialog da
chamada, `temposTocados` sobrevivia à troca de turma e de data, então o
formulário mandava o bloco da turma anterior. E a falha de
`/tempos-aula/` caía no default do backend ("um tempo"), confundindo "não
tem catálogo" com "o catálogo não carregou" — agora trava o envio, ao
contrário da falha de `/grade-aulas/`, que segue não travando.

### 6.2 Duas decisões da fatia 5 que não estavam previstas aqui

**O substituto do campo chama-se `dias_grade`, não `dias_semana`.** É
derivado da grade e read-only, no molde do `ano_letivo` do mesmo
serializer. O nome mudou de propósito: um read-only com o nome do campo
removido aceitaria um PATCH e o descartaria em silêncio, e quem editasse
os dias por ali concluiria que salvou. Vem anotado com
`Coalesce(ArrayAgg(...), [])` no viewset — anotado porque a ficha do
professor lista todos os vínculos dele e ler no serializer seria uma query
por linha (tem `assertNumQueries` travando), e com `Coalesce` porque
`ArrayAgg` devolve `NULL` em vez de lista vazia quando o vínculo não tem
slot, e o front itera o valor.

**A agenda do diário desduplica o dia.** A grade tem uma linha por tempo,
então um dia de bloco duplo aparece duas vezes nela; o diário é por dia
(§2.8), e sem o `set` a agenda mostraria a mesma aula duas vezes e a
direção conferiria em dobro. Tem teste travando.
