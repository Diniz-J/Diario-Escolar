"""Modelos da app avaliacao.

Quatro modelos compõem a frente de avaliação:

- `PeriodoAvaliativo` — esqueleto temporal (bimestre/trimestre/semestre).
- `Avaliacao` — uma prova, trabalho ou atividade avaliativa lançada por
  um professor pra uma turma+disciplina, alocada num período pela data.
- `NotaAvaliacao` — nota individual por aluno numa avaliação.
- `NotaPeriodo` — média final por (aluno, disciplina, período). Digitada
  manualmente pelo professor; é o que vai no boletim.

Decisão de design: **o sistema NÃO calcula média.** Armazena nota
individual de cada avaliação + média final POR período POR disciplina
(`NotaPeriodo`) que o professor digita manualmente. Frequência é a
ÚNICA agregação automática — é objetiva, sem regra de negócio.
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.common.models import BaseModelEscopado


class PeriodoAvaliativo(BaseModelEscopado):
    """Bimestre/trimestre/semestre de uma escola num ano letivo.

    Modelado como faixa temporal `[data_inicio, data_fim]` em vez de
    "número do bimestre" pra acomodar trimestre/semestre sem ter que
    refatorar — cada escola configura quantos períodos quiser, com
    nomes e datas próprias.

    Unique por `(escola, nome, ano_letivo)` e por `(escola, ordem,
    ano_letivo)`: não dá pra ter "1º Bimestre" repetido nem dois
    períodos com a mesma ordem no mesmo ano.

    `clean()` impede sobreposição de datas: cadastrar "1º Bim 01/02–30/04"
    e "2º Bim 15/04–30/06" na mesma escola+ano levanta `ValidationError`
    — esses 15 dias de overlap quebrariam a regra de alocação automática
    de Avaliacao por data (cada avaliação pertence a UM período).

    Soft delete via `ativo=False`. Não pode hard delete uma vez que
    `Avaliacao`/`NotaPeriodo` apontarem pra ele (FK `PROTECT`).
    """

    nome = models.CharField(
        max_length=50,
        help_text="Ex.: '1º Bimestre', '2º Trimestre', '1º Semestre'.",
    )
    ordem = models.PositiveSmallIntegerField(
        help_text="Posição sequencial no ano (1, 2, 3...).",
    )
    ano_letivo = models.PositiveIntegerField()
    data_inicio = models.DateField()
    data_fim = models.DateField()
    ativo = models.BooleanField(default=True)

    # Sobrescreve o campo herdado pra expor o reverse `escola.periodos_avaliativos`.
    escola = models.ForeignKey(
        "escola.Escola",
        on_delete=models.PROTECT,
        related_name="periodos_avaliativos",
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "período avaliativo"
        verbose_name_plural = "períodos avaliativos"
        ordering = ["-ano_letivo", "ordem"]
        constraints = [
            models.UniqueConstraint(
                fields=["escola", "nome", "ano_letivo"],
                name="periodo_unique_escola_nome_ano",
            ),
            models.UniqueConstraint(
                fields=["escola", "ordem", "ano_letivo"],
                name="periodo_unique_escola_ordem_ano",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.nome} ({self.ano_letivo}) — {self.escola}"

    # ------------------------------------------------------------------ #
    # Estado (vazio / em uso / fechado)                                   #
    # ------------------------------------------------------------------ #

    ESTADO_VAZIO = "vazio"
    ESTADO_EM_USO = "em_uso"
    ESTADO_FECHADO = "fechado"

    @property
    def estado(self) -> str:
        """Computa o estado do período em função dos dependentes.

        - `fechado`: pelo menos uma `NotaPeriodo` com `nota_final`
          preenchida — média final do bimestre já foi lançada pra
          algum aluno. Hoje **não trava** edição (decisão de produto);
          é só sinalização visual.
        - `em_uso`: existe `Avaliacao` apontando, mas nenhuma
          `NotaPeriodo` fechada ainda — provas lançadas, médias ainda
          não consolidadas.
        - `vazio`: nenhuma `Avaliacao` no período. Edição totalmente
          livre.

        Quando virar "fechado", a UI vai marcar com badge específico
        pra alertar o usuário, mas datas/ordem continuam editáveis até
        a próxima decisão de produto (Diniz disse: 'por enquanto não
        precisa fechar').
        """
        # `NotaPeriodo` exige `nota_final` não-null pra contar como
        # lançada (registros auto-criados ficam com null e não
        # caracterizam estado fechado).
        if self.notas_periodo.filter(nota_final__isnull=False).exists():
            return self.ESTADO_FECHADO
        if self.avaliacoes.exists():
            return self.ESTADO_EM_USO
        return self.ESTADO_VAZIO

    # ------------------------------------------------------------------ #
    # Validação                                                          #
    # ------------------------------------------------------------------ #

    def clean(self) -> None:
        """Valida ordenação de datas e ausência de sobreposição.

        Não-sobreposição é a regra crítica: duas faixas se sobrepõem
        quando `inicio_1 <= fim_2 AND inicio_2 <= fim_1`. Verificamos
        no escopo `(escola, ano_letivo)`, excluindo o próprio registro
        em edições.
        """
        super().clean()
        errors: dict[str, str] = {}

        if self.data_inicio and self.data_fim:
            if self.data_inicio >= self.data_fim:
                errors["data_fim"] = (
                    "A data de fim precisa ser posterior à data de início."
                )
            elif self.escola_id and self.ano_letivo:
                # Procura conflito de faixa no mesmo escopo escola+ano.
                conflito_qs = PeriodoAvaliativo.objects.filter(
                    escola_id=self.escola_id,
                    ano_letivo=self.ano_letivo,
                    data_inicio__lte=self.data_fim,
                    data_fim__gte=self.data_inicio,
                )
                if self.pk:
                    conflito_qs = conflito_qs.exclude(pk=self.pk)
                conflito = conflito_qs.first()
                if conflito is not None:
                    errors["data_inicio"] = (
                        f"As datas se sobrepõem ao período "
                        f"'{conflito.nome}' ({conflito.data_inicio} → "
                        f"{conflito.data_fim})."
                    )

        if errors:
            raise ValidationError(errors)

    # ------------------------------------------------------------------ #
    # Helper de domínio                                                   #
    # ------------------------------------------------------------------ #

    def contem(self, data: date) -> bool:
        """Indica se `data` cai dentro deste período (inclusivo)."""
        return self.data_inicio <= data <= self.data_fim


# ===================================================================== #
# Avaliacao + NotaAvaliacao                                              #
# ===================================================================== #


class Avaliacao(BaseModelEscopado):
    """Prova, trabalho ou atividade avaliativa de uma turma+disciplina.

    Substitui conceitualmente o antigo `apps.tarefas.Tarefa`. Toda
    Avaliacao **vale nota** (não tem mais `vale_nota=False`); pra
    "registrar o que foi dado em aula" sem componente de nota, esperar
    a entidade `Aula` em frente futura.

    `periodo` é alocado automaticamente no `save()` a partir da `data`:
    procura o `PeriodoAvaliativo` da mesma escola+ano cuja faixa
    contém a data. Se nenhum encontrar, `periodo=NULL` (decisão
    consciente — permite registrar avaliações fora de período sem
    bloquear o fluxo; a UI sinaliza pra escola cadastrar o período).

    Auto-cria uma `NotaAvaliacao(nota=NULL)` por aluno ativo da turma
    quando criada (no viewset `perform_create`, espelhando o padrão de
    Presença → ItemPresenca). Aluno que entra DEPOIS na turma não
    ganha NotaAvaliacao retroativamente — vai precisar ser incluído
    manualmente (`POST /avaliacoes/{id}/incluir-aluno/` em PR futuro).
    """

    class Tipo(models.TextChoices):
        PROVA = "prova", "Prova"
        TRABALHO = "trabalho", "Trabalho"
        ATIVIDADE = "atividade", "Atividade"
        PARTICIPACAO = "participacao", "Participação"

    turma = models.ForeignKey(
        "escola.Turma", on_delete=models.PROTECT, related_name="avaliacoes"
    )
    disciplina = models.ForeignKey(
        "escola.Disciplina",
        on_delete=models.PROTECT,
        related_name="avaliacoes",
    )
    professor = models.ForeignKey(
        "escola.Professor",
        on_delete=models.PROTECT,
        related_name="avaliacoes",
        null=True,
        blank=True,
    )
    # `periodo` é alocado automaticamente; pode ficar NULL se a data não
    # cai em nenhum período cadastrado. Não é chave única — a unicidade
    # vem do conjunto (turma, disciplina, titulo, data).
    periodo = models.ForeignKey(
        PeriodoAvaliativo,
        on_delete=models.PROTECT,
        related_name="avaliacoes",
        null=True,
        blank=True,
    )

    titulo = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    tipo = models.CharField(
        max_length=20,
        choices=Tipo.choices,
        default=Tipo.PROVA,
    )
    # Indexado: filtro de período (`?data_inicio=&data_fim=`), ordering
    # default (-data) e lookup do save() pra alocar `periodo`.
    data = models.DateField(default=date.today, db_index=True)
    nota_maxima = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Valor de referência da avaliação (ex.: 10,00).",
    )
    peso = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("1"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Peso pra média ponderada — usado pela escola fora do sistema.",
    )
    # Indexado: filtro padrão de listagens esconde inativas (`ativo=True`).
    ativo = models.BooleanField(default=True, db_index=True)

    escola = models.ForeignKey(
        "escola.Escola",
        on_delete=models.PROTECT,
        related_name="avaliacoes",
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "avaliação"
        verbose_name_plural = "avaliações"
        ordering = ["-data", "-criado_em"]

    def __str__(self) -> str:
        return f"{self.titulo} ({self.turma} · {self.disciplina})"

    # ------------------------------------------------------------------ #
    # Persistência — auto-aloca período pela data                        #
    # ------------------------------------------------------------------ #

    def save(self, *args, **kwargs) -> None:
        """Resolve o `periodo` em função da `data` e do `ano_letivo` da turma.

        Roda em todo save — manter o vínculo consistente quando a data
        for editada (ex.: prova remarcada cruza pra outro bimestre).
        Se nada bate, fica `None` (mais informativo que falhar; a UI
        avisa).
        """
        if self.data and self.turma_id and self.escola_id:
            # `select_related` evita um SELECT extra quando o caller já
            # carregou `turma`, mas como o save normalmente vem de
            # `Avaliacao(**dados).save()` não dá pra contar com isso.
            ano = self.turma.ano_letivo
            self.periodo = (
                PeriodoAvaliativo.objects.filter(
                    escola_id=self.escola_id,
                    ano_letivo=ano,
                    data_inicio__lte=self.data,
                    data_fim__gte=self.data,
                    ativo=True,
                )
                .order_by("ordem")
                .first()
            )
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------ #
    # Validação                                                          #
    # ------------------------------------------------------------------ #

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}

        if (
            self.turma_id
            and self.escola_id
            and self.turma.escola_id != self.escola_id
        ):
            errors["turma"] = "A turma deve pertencer à mesma escola da avaliação."

        if (
            self.disciplina_id
            and self.escola_id
            and self.disciplina.escola_id != self.escola_id
        ):
            errors["disciplina"] = (
                "A disciplina deve pertencer à mesma escola da avaliação."
            )

        if (
            self.professor_id
            and self.escola_id
            and self.professor.escola_id != self.escola_id
        ):
            errors["professor"] = (
                "O professor deve pertencer à mesma escola da avaliação."
            )

        if errors:
            raise ValidationError(errors)


class NotaAvaliacao(BaseModelEscopado):
    """Nota individual de um aluno numa avaliação.

    Auto-gerada (uma por aluno ativo da turma) quando a `Avaliacao` é
    criada — o professor abre a tela e já vê todos os alunos listados,
    sem precisar adicionar um por um. `nota=NULL` significa "ainda não
    lançada"; preencher pela tela de lançamento em lote.

    `observacao` é OPCIONAL e fica **fora do boletim entregue ao
    responsável** — espaço de nota interna do professor ("aluno
    desorganizou a sala", "fez recuperação simples", etc.). Visível pra
    professor + diretor + admin + audit log.

    Audit é parte do contrato: cada mudança da nota vira snapshot via
    `HistoricalRecords` (lido pelo middleware `simple_history`). Diniz
    pediu rastreabilidade explícita porque qualquer um da escola pode
    lançar — então saber QUEM mudou X pra Y é essencial.

    Único `(avaliacao, aluno)` — não dá pra ter duas notas pro mesmo
    aluno na mesma avaliação.
    """

    avaliacao = models.ForeignKey(
        Avaliacao, on_delete=models.CASCADE, related_name="notas"
    )
    aluno = models.ForeignKey(
        "escola.Aluno",
        on_delete=models.PROTECT,
        related_name="notas_avaliacao",
    )
    # `nota=NULL` é o estado "não lançada". Preenchida via tela de
    # lançamento em lote ou edição individual. Backend não força que
    # nota <= nota_maxima — escola pode lançar nota extra (ex.: bônus).
    # Se quiser travar, ativar `clean()` mais restrito em frente futura.
    nota = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
    )
    observacao = models.CharField(
        max_length=300,
        blank=True,
        help_text="Nota interna do professor — não aparece no boletim do responsável.",
    )

    escola = models.ForeignKey(
        "escola.Escola",
        on_delete=models.PROTECT,
        related_name="notas_avaliacao",
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "nota de avaliação"
        verbose_name_plural = "notas de avaliação"
        ordering = ["aluno__nome_completo"]
        constraints = [
            models.UniqueConstraint(
                fields=["avaliacao", "aluno"],
                name="nota_avaliacao_unique_avaliacao_aluno",
            ),
        ]

    def __str__(self) -> str:
        valor = self.nota if self.nota is not None else "—"
        return f"{self.aluno} · {valor}"

    def save(self, *args, **kwargs) -> None:
        """Sincroniza `escola` com `avaliacao.escola` antes de gravar.

        Mantém coerência com `EscopoEscolaMixin` (filtra por escola_id)
        sem confiar no payload do cliente.
        """
        if self.avaliacao_id:
            self.escola_id = self.avaliacao.escola_id
        super().save(*args, **kwargs)

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}

        if self.avaliacao_id and self.aluno_id:
            if self.aluno.turma_id != self.avaliacao.turma_id:
                errors["aluno"] = (
                    "O aluno deve pertencer à turma da avaliação."
                )
            if self.aluno.escola_id != self.avaliacao.escola_id:
                errors["aluno"] = (
                    "O aluno deve pertencer à mesma escola da avaliação."
                )

        if errors:
            raise ValidationError(errors)


# ===================================================================== #
# NotaPeriodo                                                            #
# ===================================================================== #


class NotaPeriodo(BaseModelEscopado):
    """Média final por (aluno × disciplina × período).

    É o que vai no boletim entregue ao responsável. **Digitada manualmente
    pelo professor** — o sistema não calcula. A escola decide a régua
    (média ponderada, recuperação, conselho de classe, etc.) fora do
    sistema e lança o resultado aqui.

    Único por `(escola, aluno, disciplina, periodo)`: cada aluno tem UMA
    nota final pra cada disciplina em cada período.

    `nota_final = NULL` significa "ainda não lançada" — o registro pode
    ser auto-criado vazio quando o professor abre a tela de lançamento
    (endpoint `/notas-periodo/inicializar/`).

    `observacao` é OPCIONAL e fica **fora do boletim do responsável**.
    Anotação interna do professor ("recuperação simples aplicada",
    "decisão do conselho", etc.).

    Audit log via `HistoricalRecords` é parte do contrato — mudança em
    nota final é evento crítico que precisa ter quem/quando registrado
    (decisão do produto pra qualquer professor poder lançar sem perder
    rastreabilidade).
    """

    aluno = models.ForeignKey(
        "escola.Aluno",
        on_delete=models.PROTECT,
        related_name="notas_periodo",
    )
    disciplina = models.ForeignKey(
        "escola.Disciplina",
        on_delete=models.PROTECT,
        related_name="notas_periodo",
    )
    periodo = models.ForeignKey(
        PeriodoAvaliativo,
        on_delete=models.PROTECT,
        related_name="notas_periodo",
    )
    nota_final = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Média final do período — digitada pelo professor.",
    )
    observacao = models.CharField(
        max_length=300,
        blank=True,
        help_text="Nota interna do professor — não aparece no boletim do responsável.",
    )

    escola = models.ForeignKey(
        "escola.Escola",
        on_delete=models.PROTECT,
        related_name="notas_periodo",
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = "nota de período"
        verbose_name_plural = "notas de período"
        ordering = [
            "-periodo__ano_letivo",
            "periodo__ordem",
            "aluno__nome_completo",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["escola", "aluno", "disciplina", "periodo"],
                name="nota_periodo_unique_aluno_disc_periodo",
            ),
        ]
        indexes = [
            # Boletim e tela de notas finais filtram por
            # (disciplina, periodo) e cruzam com aluno na linha do
            # boletim — o composto cobre os 3 padrões de acesso comuns.
            models.Index(
                fields=["disciplina", "periodo", "aluno"],
                name="nota_periodo_idx_disc_per_alu",
            ),
        ]

    def __str__(self) -> str:
        valor = self.nota_final if self.nota_final is not None else "—"
        return f"{self.aluno} · {self.disciplina} · {self.periodo} = {valor}"

    def clean(self) -> None:
        """Garante alinhamento de escola entre aluno, disciplina e período."""
        super().clean()
        errors: dict[str, str] = {}

        if self.aluno_id and self.escola_id:
            if self.aluno.escola_id != self.escola_id:
                errors["aluno"] = (
                    "O aluno deve pertencer à mesma escola da nota."
                )

        if self.disciplina_id and self.escola_id:
            if self.disciplina.escola_id != self.escola_id:
                errors["disciplina"] = (
                    "A disciplina deve pertencer à mesma escola."
                )

        if self.periodo_id and self.escola_id:
            if self.periodo.escola_id != self.escola_id:
                errors["periodo"] = (
                    "O período deve pertencer à mesma escola."
                )

        if errors:
            raise ValidationError(errors)
