"""Modelos da app presenca.

Dois modelos relacionados:

- `RegistroPresenca` — chamada de **um bloco de tempos** de uma turma num
  dia (ver `PRESENCA.md`). Quem registra (`professor`) é opcional no
  schema porque admin/diretor também abrem a chamada, mas a view o resolve
  do usuário logado.
- `ItemPresenca` — status individual de cada aluno dentro de um registro.
  Único por `(registro, aluno)`. Status: P (presente, default), A (ausente),
  J (justificado), R (retardatário).

Quando um `RegistroPresenca` é criado pela API, a view dispara a criação
automática de um `ItemPresenca` (status=P) para cada aluno ativo da turma.

A chamada deixou de ser diária em nov/2026: `tempos` guarda quais tempos
de aula o bloco cobre (`[1, 2]` = primeiro e segundo tempos; o dia todo é
o turno inteiro), e a frequência passou a somar **carga horária** em vez
de contar dias — que é a régua da LDB. Três coisas que não se deduzem do
código, todas em `PRESENCA.md`:

**O unique `(escola, turma, data)` caiu.** A turma passa a ter várias
chamadas por dia, uma por professor/bloco. A sobreposição de tempos é
barrada no `clean()` e no serializer, não no banco: `UniqueConstraint`
não cobre interseção de array, e a alternativa (tabela filha, uma linha
por tempo) custaria um join na agregação da frequência, que hoje é uma
query só com `assertNumQueries` travando. Mesma limitação consciente da
vigência sobreposta do `PlanoCobranca` (`FINANCEIRO.md` §3.2), com o
mesmo caminho de saída anotado se virar problema.

**`disciplina` é opcional de propósito.** Nulo significa "chamada do
dia", não de uma aula — é o que faz o mesmo modelo servir fundamental I
com professor polivalente e ensino médio por matéria, requisito do
cliente whitelabel.

**Os ordinais só são validados contra o catálogo quando ele existe.** A
escola que ainda não cadastrou `TempoAula` nenhum continua lançando
chamada (é o estado de toda instalação antes da grade ser montada);
exigir o catálogo aqui travaria a chamada por causa de um cadastro que
ninguém pediu ainda.

Invariantes em `clean()` (espelhadas no serializer):

- `RegistroPresenca`: `turma.escola == escola`, `data <= hoje`,
  `professor.escola == escola` (se fornecido), `disciplina.escola ==
  escola` (se fornecida), `tempos` não vazio, sem repetição, começando
  em 1, dentro do catálogo do turno quando houver, e sem sobrepor outra
  chamada da mesma turma no mesmo dia.
- `ItemPresenca`: `aluno.turma == registro.turma`,
  `aluno.escola == registro.escola`. O campo `escola` do item é
  sincronizado com `registro.escola` no `save()` — nunca aceita payload
  manipulado.
"""
from datetime import date

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

from apps.common.models import BaseModelEscopado
from apps.escola.models import Aluno, Disciplina, Escola, Professor, Turma
from apps.grade.models import TempoAula


def tempo_unico() -> list[int]:
    """Default de `RegistroPresenca.tempos`: um tempo.

    Nomeada (e não um lambda) porque default de `ArrayField` precisa ser
    serializável pela migration. O valor **não** é cosmético: o peso de um
    item na frequência é o tamanho deste bloco, então bloco vazio faria o
    registro desaparecer do denominador em silêncio — e é esse default que
    dá à chamada criada fora da API (shell, management command, migration
    de dados) exatamente a semântica que a chamada diária tinha antes de
    nov/2026. Quem passa pela API recebe o dia todo, via `tempos_padrao`.
    """
    return [1]


def catalogo_de_tempos(turma: Turma) -> list[int]:
    """Ordinais de tempo ativos no turno da turma, crescentes.

    Lista vazia significa "esta escola ainda não cadastrou horários
    para este turno" — e não "nenhum tempo é válido". Quem valida
    trata os dois casos de forma diferente, de propósito.
    """
    if not turma or not turma.pk:
        return []
    return sorted(
        TempoAula.objects.filter(
            escola_id=turma.escola_id, turno=turma.turno, ativo=True
        ).values_list("ordem", flat=True)
    )


def tempos_padrao(turma: Turma) -> list[int]:
    """O bloco que uma chamada sem `tempos` explícito cobre: o dia todo.

    É a semântica que a chamada diária tinha antes de nov/2026, e é o que
    mantém qualquer cliente da API (a tela de chamada atual inclusa)
    funcionando sem mudança. Sem catálogo cadastrado, `[1]` — um tempo,
    igual ao que a migração atribuiu ao histórico.
    """
    return catalogo_de_tempos(turma) or [1]


def erro_de_tempos(tempos: list[int] | None, turma: Turma | None) -> str | None:
    """Valida o bloco de tempos. Devolve a mensagem, ou None se está ok.

    Compartilhada entre `clean()` e serializer pra as duas pontas não
    divergirem — são cinco checagens, e duas cópias delas é exatamente o
    que o `FINANCEIRO.md` evitou rodando o `clean()` do modelo.
    """
    if not tempos:
        return "Informe ao menos um tempo de aula."
    if any(ordem < 1 for ordem in tempos):
        return "A ordem do tempo começa em 1."
    if len(set(tempos)) != len(tempos):
        return "Há tempo repetido na chamada."

    catalogo = catalogo_de_tempos(turma) if turma else []
    # Catálogo vazio = escola sem horários cadastrados ainda: aceita o
    # ordinal como está. Exigir o cadastro aqui travaria a chamada numa
    # instalação que só não montou a grade.
    if catalogo:
        fora = sorted(set(tempos) - set(catalogo))
        if fora:
            lista = ", ".join(f"{ordem}º" for ordem in fora)
            return (
                f"O turno desta turma não tem {lista} tempo cadastrado."
            )
    return None


def tempos_sobrepostos(registro: "RegistroPresenca") -> list[int]:
    """Tempos do registro já ocupados por outra chamada da turma no dia.

    Não existe constraint de banco pra isso (ver docstring do módulo),
    então é esta consulta que impede duas chamadas cobrindo o mesmo
    tempo. Corrida entre duas requisições simultâneas passa — risco
    aceito, é um professor abrindo a chamada.
    """
    if not (registro.turma_id and registro.data and registro.tempos):
        return []
    outras = RegistroPresenca.objects.filter(
        turma_id=registro.turma_id, data=registro.data
    )
    if registro.pk:
        outras = outras.exclude(pk=registro.pk)
    ocupados: set[int] = set()
    for tempos in outras.values_list("tempos", flat=True):
        ocupados.update(tempos or [])
    return sorted(ocupados & set(registro.tempos))


class RegistroPresenca(BaseModelEscopado):
    """Chamada de uma turma num dia."""

    turma = models.ForeignKey(
        Turma, on_delete=models.PROTECT, related_name="registros_presenca"
    )
    # Indexado: filtro de período (`?data_inicio=&data_fim=`) e ordering
    # default (-data).
    data = models.DateField(default=date.today, db_index=True)
    professor = models.ForeignKey(
        Professor,
        on_delete=models.PROTECT,
        related_name="registros_presenca",
        null=True,
        blank=True,
    )
    # Ordinais dos tempos de aula cobertos por esta chamada (1 = primeiro
    # tempo do turno). Guarda ordinal e não FK pro `TempoAula` porque o
    # registro é dono do próprio dado: mexer no catálogo de horários não
    # pode reescrever chamada passada (`PRESENCA.md` §2.1 e §2.9).
    tempos = ArrayField(
        models.PositiveSmallIntegerField(),
        default=tempo_unico,
        blank=True,
    )
    # Nulo = chamada do dia (fundamental I, professor polivalente); com
    # disciplina = chamada de uma aula (ensino médio por matéria).
    disciplina = models.ForeignKey(
        Disciplina,
        on_delete=models.PROTECT,
        related_name="registros_presenca",
        null=True,
        blank=True,
    )
    observacao = models.TextField(blank=True)

    # Sobrescreve o campo herdado para expor `escola.registros_presenca`.
    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="registros_presenca"
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "registro de presença"
        verbose_name_plural = "registros de presença"
        ordering = ["-data"]
        indexes = [
            # Era a ponta do unique que caiu; segue sendo o filtro mais
            # comum (a chamada de uma turma num dia) e agora devolve
            # várias linhas, uma por bloco de tempos.
            models.Index(
                fields=["turma", "data"],
                name="presenca_idx_turma_data",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.turma} — {self.data}"

    def clean(self) -> None:
        """Coerência entre escola, turma, professor e data."""
        super().clean()
        errors: dict[str, str] = {}

        if self.turma_id and self.escola_id and self.turma.escola_id != self.escola_id:
            errors["turma"] = "A turma deve pertencer à mesma escola do registro."

        if self.data and self.data > date.today():
            errors["data"] = "Data do registro não pode estar no futuro."

        if (
            self.professor_id
            and self.escola_id
            and self.professor.escola_id != self.escola_id
        ):
            errors["professor"] = (
                "O professor deve pertencer à mesma escola do registro."
            )

        if (
            self.disciplina_id
            and self.escola_id
            and self.disciplina.escola_id != self.escola_id
        ):
            errors["disciplina"] = (
                "A disciplina deve pertencer à mesma escola do registro."
            )

        turma = self.turma if self.turma_id else None
        erro_tempos = erro_de_tempos(self.tempos, turma)
        if erro_tempos:
            errors["tempos"] = erro_tempos
        else:
            conflito = tempos_sobrepostos(self)
            if conflito:
                lista = ", ".join(f"{ordem}º" for ordem in conflito)
                errors["tempos"] = (
                    f"Já existe chamada desta turma neste dia cobrindo o "
                    f"{lista} tempo."
                )

        if errors:
            raise ValidationError(errors)


class ItemPresenca(BaseModelEscopado):
    """Status individual de presença de um aluno em um registro."""

    class Status(models.TextChoices):
        PRESENTE = "P", "Presente"
        AUSENTE = "A", "Ausente"
        JUSTIFICADO = "J", "Justificado"
        RETARDATARIO = "R", "Retardatário"

    registro = models.ForeignKey(
        RegistroPresenca, on_delete=models.CASCADE, related_name="itens"
    )
    aluno = models.ForeignKey(
        Aluno, on_delete=models.PROTECT, related_name="presencas"
    )
    status = models.CharField(
        max_length=1,
        choices=Status.choices,
        default=Status.PRESENTE,
    )
    observacao = models.CharField(max_length=200, blank=True)

    # `escola` é derivada do registro pai — ver `save()` abaixo.
    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="itens_presenca"
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "item de presença"
        verbose_name_plural = "itens de presença"
        ordering = ["aluno__nome_completo"]
        constraints = [
            models.UniqueConstraint(
                fields=["registro", "aluno"],
                name="item_presenca_unique_registro_aluno",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.aluno} — {self.get_status_display()}"

    def save(self, *args, **kwargs) -> None:
        """Sincroniza `escola` com `registro.escola` antes de gravar.

        O `EscopoEscolaMixin` filtra leituras por `escola_id` — para que
        funcione consistentemente, `item.escola` precisa refletir
        exatamente a escola do registro pai. Forçar aqui evita qualquer
        possibilidade de divergência por payload manipulado ou erro
        humano.
        """
        if self.registro_id:
            self.escola_id = self.registro.escola_id
        super().save(*args, **kwargs)

    def clean(self) -> None:
        """Coerência entre aluno, registro e suas turmas/escolas."""
        super().clean()
        errors: dict[str, str] = {}

        if self.registro_id and self.aluno_id:
            if self.aluno.turma_id != self.registro.turma_id:
                errors["aluno"] = (
                    "O aluno deve pertencer à turma do registro de presença."
                )
            if self.aluno.escola_id != self.registro.escola_id:
                errors["aluno"] = (
                    "O aluno deve pertencer à mesma escola do registro."
                )

        if errors:
            raise ValidationError(errors)
