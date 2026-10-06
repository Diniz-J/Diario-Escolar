"""Modelos da app comunicados.

Um `Comunicado` é um aviso institucional da escola para os responsáveis
dos alunos — reunião de pais, feriado, campanha de vacinação, etc. É o
oposto da `Ocorrencia`: não fala de um aluno específico, fala com um
público (a escola inteira ou turmas selecionadas).

Ciclo de vida (`status`):

    rascunho ──(POST /comunicados/{id}/enviar/)──> enviando ──> enviado
                                                            └──> falhou

`rascunho` é o estado inicial e o único editável/excluível: email não tem
"desfazer", então salvar NUNCA dispara envio. O disparo é uma ação
explícita e separada, e a partir dela o comunicado fica imutável — é
registro histórico do que saiu para os pais.

`ComunicadoDestinatario` materializa uma linha por aluno alcançado, com o
resultado do envio daquele endereço. Serve pra responder a pergunta que a
secretaria sempre faz ("o responsável do João recebeu?") e pra expor quem
está sem email cadastrado.
"""
from django.db import models
from simple_history.models import HistoricalRecords

from apps.common.models import BaseModelEscopado, TimeStampedModel
from apps.escola.models import Aluno, Escola, Turma


class Comunicado(BaseModelEscopado):
    """Aviso enviado por email aos responsáveis dos alunos."""

    class Destino(models.TextChoices):
        ESCOLA = "escola", "Toda a escola"
        TURMAS = "turmas", "Turmas selecionadas"

    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        ENVIANDO = "enviando", "Enviando"
        ENVIADO = "enviado", "Enviado"
        FALHOU = "falhou", "Falhou"

    titulo = models.CharField(max_length=200)
    mensagem = models.TextField()

    destino = models.CharField(
        max_length=10,
        choices=Destino.choices,
        default=Destino.ESCOLA,
    )
    # Só usado quando `destino="turmas"`. Em `destino="escola"` fica vazio
    # (o envio resolve a escola inteira na hora do disparo, não aqui — ver
    # services.resolver_alunos). `blank=True` porque M2M não aceita null.
    turmas = models.ManyToManyField(
        Turma, related_name="comunicados", blank=True
    )

    # Indexado: a listagem separa rascunhos de enviados e o filtro por
    # status é o padrão da página.
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.RASCUNHO,
        db_index=True,
    )
    enviado_em = models.DateTimeField(null=True, blank=True)

    # Autoria: quem escreveu e quem apertou o botão podem ser pessoas
    # diferentes (secretaria redige, diretor dispara). SET_NULL pra que
    # desativar/remover um usuário não apague o histórico do comunicado.
    criado_por = models.ForeignKey(
        "accounts.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comunicados_criados",
    )
    enviado_por = models.ForeignKey(
        "accounts.Usuario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comunicados_enviados",
    )

    # Contadores consolidados do disparo. Redundantes com a agregação de
    # `destinatarios`, e isso é proposital: a listagem mostra "142 enviados
    # / 3 falhas" sem precisar de subquery por linha.
    total_destinatarios = models.PositiveIntegerField(default=0)
    total_enviados = models.PositiveIntegerField(default=0)
    total_falhas = models.PositiveIntegerField(default=0)
    total_sem_email = models.PositiveIntegerField(default=0)

    # Sobrescreve o campo herdado para expor `escola.comunicados` no reverse.
    escola = models.ForeignKey(
        Escola, on_delete=models.PROTECT, related_name="comunicados"
    )

    history = HistoricalRecords(m2m_fields=[turmas])

    class Meta:
        verbose_name = "comunicado"
        verbose_name_plural = "comunicados"
        ordering = ["-criado_em"]
        indexes = [
            # Listagem é sempre escopada por escola e ordenada por recência.
            models.Index(
                fields=["escola", "-criado_em"],
                name="comunicado_idx_escola_criado",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.titulo} — {self.get_status_display()}"

    @property
    def editavel(self) -> bool:
        """Só rascunho pode ser alterado/excluído.

        Depois do disparo o comunicado é registro do que efetivamente
        chegou na caixa de entrada dos pais — editar criaria divergência
        entre o que o sistema mostra e o que foi lido.
        """
        return self.status == self.Status.RASCUNHO


class ComunicadoDestinatario(TimeStampedModel):
    """Resultado do envio de um comunicado para o responsável de um aluno.

    Uma linha por aluno alcançado (não por endereço): irmãos na mesma
    escola compartilham o email do responsável, e o envio deduplica por
    endereço — mas as duas linhas existem e recebem o mesmo resultado, pra
    que a busca por aluno responda "o responsável do João recebeu?".

    Não herda `BaseModelEscopado`: a escola vem por `comunicado.escola`, e
    duplicar a FK aqui abriria espaço pra divergência.
    """

    class Status(models.TextChoices):
        # Estado inicial: a linha é criada ANTES do envio. Se o processo
        # morrer no meio do disparo, as linhas que sobraram em `pendente`
        # mostram exatamente onde parou — em vez de desaparecerem.
        PENDENTE = "pendente", "Pendente"
        ENVIADO = "enviado", "Enviado"
        FALHOU = "falhou", "Falhou"
        SEM_EMAIL = "sem_email", "Sem email cadastrado"

    comunicado = models.ForeignKey(
        Comunicado, on_delete=models.CASCADE, related_name="destinatarios"
    )
    aluno = models.ForeignKey(
        Aluno, on_delete=models.PROTECT, related_name="comunicados_recebidos"
    )
    # Snapshot do email/nome no momento do disparo. Se o cadastro do aluno
    # mudar depois, o log continua mostrando pra onde a mensagem foi de
    # fato — auditoria tem que ser imutável.
    email = models.EmailField(blank=True)
    nome_responsavel = models.CharField(max_length=200, blank=True)

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDENTE
    )
    # Mensagem de erro do provedor quando `status="falhou"` — é o que
    # permite distinguir "email inválido" de "cota do provedor estourada".
    erro = models.TextField(blank=True)
    enviado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "destinatário de comunicado"
        verbose_name_plural = "destinatários de comunicado"
        ordering = ["aluno__nome_completo"]
        constraints = [
            models.UniqueConstraint(
                fields=["comunicado", "aluno"],
                name="comunicado_dest_unique_comunicado_aluno",
            ),
        ]
        indexes = [
            # A tela de log filtra por status ("mostre só as falhas").
            models.Index(
                fields=["comunicado", "status"],
                name="comunicado_dest_idx_com_status",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.aluno} → {self.email or '(sem email)'} ({self.get_status_display()})"
