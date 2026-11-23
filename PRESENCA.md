# PRESENCA.md — Presença por tempo de aula + grade horária

Desenho da migração da presença **diária** para presença **por tempo de
aula**, com grade horária por turma. Decidido em nov/2026.

---

## 1. O que muda

Hoje a chamada é uma por `(escola, turma, data)` e a frequência conta
**itens** — o denominador é "dias com chamada". Passa a ser uma chamada
por **bloco de tempos** de uma turma num dia, e a frequência soma
**tempos** — o denominador é carga horária, que é a régua da LDB (75% da
carga, não dos dias).

Três coisas entram juntas: o bloco de tempos no registro, o professor
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
| migração | registros existentes recebem `tempos=[1]`, disciplina nula |

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
lugares que calculam isso mudam juntos, na mesma PR:

- `apps/boletins/services.py::calcular_frequencia`
- `apps/relatorios/services.py` — frequência por turma (atenção ao
  `assertNumQueries`) e presença média do dashboard
- `_STATUS_EFETIVOS` deixa de ser lista de status e vira tabela de pesos

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
| 1 | Grade — backend | este doc, `TempoAula`, `AulaGrade`, migration, admin, API só-direção |
| 2 | Grade — frontend | tela de montagem por turma/ano letivo + clonar do ano anterior |
| 3 | Presença por tempo | §3.3 **mais** a régua da §4 — indivisível: separar deixa a frequência errada em produção entre os merges |
| 4 | Tela de chamada | tempos pré-marcados pela grade, modo dia-todo, ajuste manual |
| 5 | Aposentar `dias_semana` | `projetar_agenda` lê a grade; campo removido em migration |

Ordem: grade antes da presença, pra a tela de chamada (fatia 4) nascer
já com a sugestão e não ser reescrita.
