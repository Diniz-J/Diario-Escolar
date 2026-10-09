# RESPONSAVEIS.md — Convergência do responsável

Desenho da frente que faz o **email sair pelos vínculos** (`ResponsavelAluno`)
em vez do campo de texto do aluno, e que dá à secretaria como cadastrar o
segundo responsável.

É a "fatia posterior" que o [`PORTAL.md`](./PORTAL.md) §3 prometeu quando
decidiu manter `Aluno.email_responsavel` como destino na v1 do portal:

> O campo de texto continua existindo e continua sendo o destino do email
> de comunicado e de ocorrência na v1. Não troco o que funciona em produção
> no mesmo passo que crio o modelo novo. A duplicidade é consciente e
> temporária; convergir é fatia posterior.

Leia junto com o `PORTAL.md` (modelo de dados e segurança do portal) e o
`CLAUDE.md` (guardrails do repositório).

---

## 1. O problema

O sistema tem **duas noções de responsável** e elas não conversam:

| | Fonte | Quem usa |
|---|---|---|
| Campo de texto | `Aluno.nome_responsavel` + `Aluno.email_responsavel` | email de ocorrência (`apps/ocorrencias/services.py`), email de comunicado (`apps/comunicados/services.py`) |
| Vínculo | `ResponsavelAluno` (M2M `Responsavel` × `Aluno`) | todo o portal do responsável |

Consequência: **o responsável vinculado só pelo `ResponsavelAluno` vê os
dados no portal e nunca recebe email.** Mãe e pai cadastrados, só um
recebe a ocorrência. O modelo suporta múltiplos responsáveis desde a
fatia 1 do portal; o envio nunca soube disso.

O `CLAUDE.md` registra isso como pendência da FASE 4 desde a entrega do
email em produção: "Falta: múltiplos responsáveis, telefone, flag
`recebe_notificacao`".

### Por que está latente hoje

A divergência existe no código mas quase não aparece em produção, por um
motivo que importa pro escopo:

1. `manage.py portal_semear_responsaveis` cria **um `Responsavel` por
   (escola, email normalizado)** a partir do próprio
   `Aluno.email_responsavel`. Numa escola semeada, o conjunto de emails
   vindo dos vínculos é **idêntico** ao do campo do aluno.
2. A divergência só nasce quando alguém cria um segundo responsável — e
   hoje isso **só é possível pelo `/admin/` do Django**. Não há tela.

Ou seja: a capacidade está no modelo e ninguém consegue exercitá-la. É por
isso que a tela de vínculos entra no escopo (decisão em §3) — sem ela, o
backend novo seria maquinário que só o admin global aciona.

---

## 2. Obstáculo estrutural: `ComunicadoDestinatario`

A tabela de log de entrega tem hoje **uma linha por aluno**:

```python
# apps/comunicados/models.py
constraints = [
    models.UniqueConstraint(
        fields=["comunicado", "aluno"],
        name="comunicado_dest_unique_comunicado_aluno",
    ),
]
```

com snapshot de `email` e `nome_responsavel` no momento do disparo, e
dedup por endereço na hora do envio (irmãos compartilham o email do
responsável → duas linhas de log, uma mensagem).

Mandar para dois responsáveis exige **dois resultados de entrega** ("a mãe
recebeu, o pai falhou"), então uma linha por aluno deixa de servir. Isso é
migration em tabela **com dado de produção** (comunicados já enviados,
validados em 2026-05-30) e muda a semântica do log — ver a fatia 3.

---

## 3. Decisões tomadas

Decididas com o Diniz antes de começar; registradas pra não reabrir.

**Escopo: backend + tela de vínculos.** As três fatias de backend mais a UI
pra adicionar/remover responsável de um aluno. Sem a tela, a secretaria
nunca cria o segundo responsável e a correção fica invisível na prática
(ver §1).

**`recebe_notificacao` mora no `Responsavel`, não no vínculo.** "Não quero
receber email" é da pessoa, não da relação com cada filho. Ninguém pediu
granularidade por filho, e a opção por vínculo multiplicaria a UI sem
caso de uso.

**`recebe_notificacao` é separado de `ativo`.** Desligar o opt-out para de
mandar email mas **mantém o acesso ao portal**: o pai que não quer email
ainda quer consultar o boletim. Confundir os dois tiraria o acesso de
quem só pediu silêncio.

**Fallback para o campo de texto, com uma regra precisa** — ver §4.1, é a
armadilha central desta frente.

**O campo `Aluno.email_responsavel` NÃO é removido agora.** Ele segue como
fallback e como entrada do cadastro (é o que a secretaria digita, e é de
onde a semeadura parte). Removê-lo é uma terceira frente, que exigiria
mexer no `AlunoResource` (import/export), no `AlunoFormDialog` e no
`contar_previa`. Fora de escopo.

---

## 4. Invariantes

### 4.1. O fallback dispara por ausência de vínculo, nunca por ausência de destino

A regra que parece igual e não é:

- Aluno com **zero** `ResponsavelAluno` → usa `Aluno.email_responsavel`.
  É a escola que nunca rodou a semeadura; sem isso ela **pararia de
  receber email em silêncio**, que é a pior falha possível aqui.
- Aluno **com** vínculos, mas nenhum elegível (todos inativos ou com
  `recebe_notificacao=False`) → **zero destinos, sem fallback**.

Cair no campo do aluno no segundo caso reenviaria para a mesma pessoa que
acabou de pedir pra não receber — transformando o opt-out em nada. A
diferença entre "não há cadastro" e "o cadastro diz não" tem que
sobreviver no código.

Teste obrigatório nos dois sentidos.

### 4.2. Dedup continua por endereço normalizado

Irmãos compartilham responsável, então o envio deduplica por
`normalizar_email()` — mesma regra do `apps/common/texto.py` que o
comunicado e o portal já usam. Sem isso, o mesmo endereço recebe o mesmo
comunicado duas vezes, e a cota de 300/dia do Brevo é compartilhada entre
ocorrência, comunicado e convite.

> **Corrigido na fatia 1.** Esta seção supunha também o casal que usa uma
> conta só, gerando dois destinos iguais para o **mesmo** aluno. Isso não
> acontece: o unique por `(escola, email)` do `Responsavel` recusa a
> segunda conta, e todo responsável de um aluno é da mesma escola dele.
> A dedup que importa é entre irmãos, e ela mora no agrupamento por
> endereço do comunicado (`_agrupar_por_email`), não em
> `destinatarios.py`. O módulo mantém uma dedup por aluno como rede, com
> o motivo real escrito no código: `ResponsavelAluno.objects.create()`
> não passa por `clean()`, então um vínculo cruzando escola feito por
> shell traria um endereço repetido.

### 4.3. Escopo de escola

`ResponsavelAluno.clean()` já exige `responsavel.escola == aluno.escola`.
Qualquer consulta nova de destinatário parte do aluno e atravessa o
vínculo — nunca monta lista por email solto, que cruzaria escolas no
mesmo endereço.

### 4.4. O log de entrega não pode perder histórico

A migration da fatia 3 roda sobre comunicados já enviados em produção. As
linhas existentes têm que continuar respondendo "o responsável do João
recebeu?" depois da mudança. Isso é critério de aceite, não detalhe.

---

## 5. Fatias

Uma PR por fatia, na ordem. As três primeiras são backend e saíram de
`main`; a quarta esperou o #117 (ver §6).

| # | Fatia | Verificação | Status |
|---|---|---|---|
| 1 | `apps/portal/destinatarios.py` — origem única do destinatário | Aluno sem vínculo recebe pelo campo antigo; aluno com dois vínculos gera dois destinos; irmãos com o mesmo responsável deduplicam; consulta em lote não faz N+1 | ✅ PR #120 |
| 2 | `recebe_notificacao` no `Responsavel` + migration | Desligar exclui do envio e **mantém** o acesso ao portal; aluno cujos vínculos todos recusaram não cai no fallback | ✅ PR #121 |
| 3 | `ComunicadoDestinatario` por responsável + migration | Comunicado já enviado mantém o log intacto; dois responsáveis geram duas linhas; `contar_previa` bate com o que sai | ✅ PR #122 |
| 4 | Tela de vínculos no staff | Secretaria adiciona e remove responsável de um aluno; não cria vínculo cruzando escola; professor não acessa | ✅ |

### Fatia 1 — `destinatarios.py`

Módulo em `apps/portal/`, porque é onde o vínculo mora. Expõe duas
funções: uma por aluno (ocorrência, um aluno por vez) e uma **em lote**
(comunicado, centenas de alunos — uma consulta, não uma por aluno). O
retorno carrega email, nome e o id do responsável quando houver, porque a
fatia 3 precisa saber de quem foi a entrega.

`apps/ocorrencias/services.py` e `apps/comunicados/services.py` passam a
chamar isso. O `montar_email_*` de cada um não muda.

> **Ajuste na entrega.** Só a ocorrência trocou de origem na fatia 1. O
> comunicado foi junto com a fatia 3, porque enquanto o log tinha uma linha
> por aluno ele não conseguia registrar duas entregas — passar a resolver
> dois destinos antes disso faria a prévia prometer duas mensagens e sair
> uma. As duas mudanças são inseparáveis.

Atenção ao `contar_previa` do comunicado: ele alimenta o diálogo de
confirmação ("este comunicado vai para 142 responsáveis") e o aviso de
cadastro incompleto. Com múltiplos responsáveis, `total_alunos` e
`total_emails` deixam de ter a relação que tinham — a prévia precisa
continuar honesta sobre quantas **mensagens** saem, que é o que consome
cota.

### Fatia 3 — a migration

O caminho que preserva histórico: adicionar FK `responsavel` **nullable**,
trocar o unique para incluí-la, e deixar as linhas antigas com
`responsavel=NULL` (foram enviadas quando o conceito não existia). O
snapshot de `email`/`nome_responsavel` que já existe é o que mantém essas
linhas legíveis.

Não apagar nem reescrever linha antiga. Não tornar a FK obrigatória.

> **Detalhe que só apareceu implementando.** O unique novo precisa de
> `nulls_distinct=False` (Postgres 15+; o projeto fixa `postgres:16` no
> compose, no CI e em produção). No padrão do Postgres, NULL é distinto de
> NULL num unique, então duas linhas `(comunicado, aluno, NULL)` passariam
> e a idempotência da materialização — que depende de `ignore_conflicts` —
> se perderia justamente no caminho do fallback, mandando o comunicado em
> dobro pra escola sem vínculo.

> **Efeito colateral no portal.** `alunos_por_comunicado` faz join no log,
> então um filho com mãe e pai vinculados passou a aparecer duas vezes no
> mesmo aviso dentro do portal do pai. Precisou de `distinct()`.

### Fatia 4 — a tela, e o que ela precisou abrir a mais

O escopo desta seção era "adiciona e remove responsável de um aluno", que
se lê como só vincular. **Não bastava.** A semeadura cria uma conta por
email tirado do `Aluno.email_responsavel`, ou seja uma por família, então
vincular contas existentes nunca produz o caso mãe-e-pai — sem criar conta
aqui, o segundo responsável continuaria nascendo só no `/admin/` e as três
fatias anteriores seguiriam inalcançáveis pra quem opera a escola. Era o
§1 desta doc dizendo uma coisa e o §5 outra; a decisão (out/2026) foi
seguir o §1.

Isso **reverteu** a nota do 6b que fazia o `ResponsavelStaffViewSet`
somente-leitura ("conta de usuário externo não nasce pela API do staff").
O motivo está no `ResponsavelCriacaoSerializer`, e o teste que fixava a
decisão antiga foi reescrito, não apagado — ele agora fixa a afirmação
mais estreita que continua valendo: cadastro entrou, **edição e remoção
não**. Corrigir email errado segue pelo admin; apagar responsável é
`PROTECT` dos dois lados.

O que a reversão não afrouxa: a conta nasce sem senha utilizável, então
cadastrar não dá acesso a nada. O acesso continua vindo só do convite.

**O guard do vínculo tem duas camadas, e nenhuma substitui a outra.** O
`clean()` do model exige que responsável e aluno concordem entre si; o
serializer checa **cada lado contra a escola de quem está logado**. O caso
que só a segunda camada pega: responsável e aluno ambos de outra escola —
eles concordam, o `clean()` fica calado, e sem o guard por lado um diretor
criaria esse vínculo e ganharia acesso aos dados de uma criança alheia.
Tem teste próprio, e remover qualquer um dos dois guards derruba três.

Detalhes que só apareceram implementando:

- **O escopo da listagem filtra os dois lados.** Redundante enquanto o
  invariante vale, e é por isso que está lá: `objects.create()` não passa
  por `clean()`, então um vínculo cruzado por shell existe em teoria, e
  filtrar só pelo responsável mostraria a um diretor o nome de um aluno de
  outra escola.
- **O email é normalizado no serializer, não só no `save()`.** O model
  normaliza depois da validação, então `Maria@Example.com` passava pelo
  `UniqueTogetherValidator` (que compara o valor cru contra o banco, onde
  está `maria@example.com`) e só estourava no INSERT — 500 em vez de 400.
- **A listagem do vínculo exige `?responsavel=` ou `?aluno=`** em vez de
  paginar (`FiltroEscopoObrigatorioMixin`), mesma escolha dos endpoints
  matriz: a tela sempre pede os filhos de uma família.
- **Sem `PUT`/`PATCH` no vínculo.** Trocar um lado do par é outro vínculo;
  apagar e criar mantém o histórico auditado legível.

Na UI, a consequência que não é óbvia e está escrita na tela: **remover o
último vínculo não silencia o aluno** — pelo §4.1, zero vínculos faz o
email voltar a sair pelo campo de texto do cadastro. Sem avisar, a
secretaria lê "removido" como "silenciado".

---

## 6. Sequência e dependências

**A fatia 4 dependia do PR #117** — o lugar natural da tela de vínculos é
a tela "Responsáveis" (`/responsaveis`), que nasceu lá, e até mergear não
havia onde pendurar a UI. O #117 entrou em out/2026 e a fatia saiu em
seguida.

**As fatias 1–3 não dependiam de nada aberto** e já estão na `main`
(PRs #120–#122). Checado na época: não tocam em nenhum arquivo do #117
(portal: `views_staff.py`, `urls_staff.py`, `serializers.py`,
`ConviteResponsavel`) nem do #118 (`relatorios`, `common/planilha.py`,
`boletins/views.py`, `escola/views.py`, `ocorrencias/views.py`). A fatia 2
tocou `apps/portal/models.py`, que o #117 também toca — classes diferentes
(`Responsavel` vs `ConviteResponsavel`), então o #117 deve rebasear sem
briga.

---

## 7. Fora de escopo (registrado pra não virar discussão de novo)

- **Remover `Aluno.nome/email_responsavel`.** Ver §3.
- **Telefone do responsável.** Está na mesma linha de pendência do
  `CLAUDE.md`, mas é outro canal (SMS/WhatsApp) e outro provedor. Nada
  aqui o bloqueia.
- **Granularidade de opt-out por filho.** Ver §3.
- **Notificar responsável de aluno inativo.** A regra atual do portal
  (`PORTAL.md`) é que o aluno desativado mantém o histórico mas para de
  receber comunicado novo. Esta frente não muda isso.

---

## 8. Estado

**Frente completa** (out/2026). Fatias 1–3 nos PRs #120, #121 e #122: o
destino do email é o vínculo, o opt-out existe e o log do comunicado
registra uma entrega por responsável. Fatia 4 fecha o ciclo: a secretaria
cadastra o segundo responsável e gerencia os vínculos pela tela
`/responsaveis`, sem `/admin/`.

O §1 ("por que está latente hoje") **deixou de valer** — era a ausência
desta tela que mantinha a capacidade inalcançável. Fica como registro do
raciocínio que decidiu o escopo.

Pendências que esta frente não cobriu, por escolha registrada no §7:
telefone do responsável (outro canal, outro provedor), remover
`Aluno.nome/email_responsavel` e opt-out por filho. E uma que a fatia 4
deixou de fora de propósito: **editar nome/email de responsável pela tela**
— corrigir email errado segue pelo `/admin/`, como o 6b documentou.
