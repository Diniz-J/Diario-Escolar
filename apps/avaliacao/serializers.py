"""Serializers da app avaliacao."""
from rest_framework import serializers

from apps.common.serializers import (
    AutoEscopoEscolaSerializerMixin,
    validate_escola_do_usuario,
)

from .models import Avaliacao, NotaAvaliacao, PeriodoAvaliativo


class PeriodoAvaliativoSerializer(
    AutoEscopoEscolaSerializerMixin, serializers.ModelSerializer
):
    """Serializa `PeriodoAvaliativo`.

    - `escola` é opcional no payload: o `AutoEscopoEscolaSerializerMixin`
      injeta a escola do JWT quando ausente. Admin global ainda escolhe
      explicitamente.
    - `estado` é exposto read-only — vem do `model.estado`. Hoje sempre
      'vazio'; nos próximos PRs vai refletir presença de avaliações e
      notas finais.
    - `validate()` chama `instance.clean()` pra disparar a regra de
      não-sobreposição/datas com mensagem clara em vez de IntegrityError.
    """

    estado = serializers.CharField(read_only=True)

    class Meta:
        model = PeriodoAvaliativo
        fields = [
            "id",
            "escola",
            "nome",
            "ordem",
            "ano_letivo",
            "data_inicio",
            "data_fim",
            "ativo",
            "estado",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "estado", "criado_em", "atualizado_em"]
        extra_kwargs = {"escola": {"required": False}}

    def validate_escola(self, value):
        return validate_escola_do_usuario(
            value,
            self.context.get("request"),
            "Você só pode criar períodos avaliativos na sua própria escola.",
        )

    def validate(self, attrs: dict) -> dict:
        """Replica `model.clean()` no nível do serializer.

        Sem isso o `full_clean` só rodaria no admin — pelo DRF, a
        sobreposição quebraria via IntegrityError genérico (ou nem
        quebraria, já que a unique constraint não cobre faixa de datas).
        """
        instance = PeriodoAvaliativo(
            escola=attrs.get("escola")
            or getattr(self.instance, "escola", None),
            nome=attrs.get("nome") or getattr(self.instance, "nome", ""),
            ordem=attrs.get("ordem") or getattr(self.instance, "ordem", 0),
            ano_letivo=attrs.get("ano_letivo")
            or getattr(self.instance, "ano_letivo", 0),
            data_inicio=attrs.get("data_inicio")
            or getattr(self.instance, "data_inicio", None),
            data_fim=attrs.get("data_fim")
            or getattr(self.instance, "data_fim", None),
        )
        # Preserva o pk em update pra que o `exclude(pk=self.pk)` da
        # validação de sobreposição funcione corretamente.
        if self.instance is not None:
            instance.pk = self.instance.pk
        try:
            instance.clean()
        except Exception as exc:
            # `clean()` levanta django.core.exceptions.ValidationError;
            # convertemos pro tipo do DRF pra resposta JSON consistente.
            from django.core.exceptions import ValidationError as DjangoVE

            if isinstance(exc, DjangoVE):
                detalhes = exc.message_dict if hasattr(exc, "message_dict") else {
                    "non_field_errors": exc.messages
                }
                raise serializers.ValidationError(detalhes) from exc
            raise
        return attrs


# ===================================================================== #
# Avaliacao + NotaAvaliacao                                              #
# ===================================================================== #


class AvaliacaoSerializer(
    AutoEscopoEscolaSerializerMixin, serializers.ModelSerializer
):
    """Serializa `Avaliacao`.

    Campos derivados expostos read-only pro frontend não precisar de
    requests adicionais:

    - `tipo_display` — label PT-BR do enum.
    - `periodo_nome` — nome do período (ou None se não alocado).
    - `turma_nome`/`disciplina_nome` — economizam JOIN no front.
    - `total_alunos`/`notas_lancadas` — métrica rápida pro card de lista
      ("3 de 24 lançadas").
    """

    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    periodo_nome = serializers.CharField(
        source="periodo.nome", read_only=True, default=None
    )
    turma_nome = serializers.CharField(source="turma.nome", read_only=True)
    disciplina_nome = serializers.CharField(
        source="disciplina.nome", read_only=True
    )
    total_alunos = serializers.SerializerMethodField()
    notas_lancadas = serializers.SerializerMethodField()

    class Meta:
        model = Avaliacao
        fields = [
            "id",
            "escola",
            "turma",
            "turma_nome",
            "disciplina",
            "disciplina_nome",
            "professor",
            "periodo",
            "periodo_nome",
            "titulo",
            "descricao",
            "tipo",
            "tipo_display",
            "data",
            "nota_maxima",
            "peso",
            "ativo",
            "total_alunos",
            "notas_lancadas",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = [
            "id",
            "periodo",
            "periodo_nome",
            "tipo_display",
            "turma_nome",
            "disciplina_nome",
            "total_alunos",
            "notas_lancadas",
            "criado_em",
            "atualizado_em",
        ]
        extra_kwargs = {"escola": {"required": False}}

    def validate_escola(self, value):
        return validate_escola_do_usuario(
            value,
            self.context.get("request"),
            "Você só pode criar avaliações na sua própria escola.",
        )

    def validate(self, attrs: dict) -> dict:
        """Garante que `escola` foi resolvida antes de ir pro banco.

        Cenário: usuário admin global (sem `escola_id` no JWT) ou
        usuário com sessão antiga onde o JWT carrega `escola_id=None`.
        Nesses casos o `AutoEscopoEscolaMixin` não injeta nada — sem
        este guard, o INSERT falha com IntegrityError 500 do Postgres
        em vez de devolver 400 com mensagem útil pra UI.

        Pra create (sem `self.instance`), `attrs["escola"]` precisa estar
        presente. Em update parcial (PATCH com `self.instance`), permite
        omitir — mantém a escola da instância.
        """
        if self.instance is None and not attrs.get("escola"):
            raise serializers.ValidationError(
                {
                    "escola": (
                        "Sua conta não está vinculada a uma escola. "
                        "Faça logout e login novamente, ou peça pra um "
                        "administrador definir sua escola."
                    )
                }
            )
        return attrs

    def get_total_alunos(self, obj: Avaliacao) -> int:
        # Conta as NotaAvaliacao da avaliação — equivale ao total de
        # alunos da turma no momento da criação (auto-geradas).
        return obj.notas.count()

    def get_notas_lancadas(self, obj: Avaliacao) -> int:
        return obj.notas.exclude(nota__isnull=True).count()


class NotaAvaliacaoSerializer(serializers.ModelSerializer):
    """Serializa `NotaAvaliacao` — só leitura e update.

    Cria via auto-geração (perform_create da Avaliacao) ou via
    `POST /avaliacoes/{id}/lancar-notas/`. `aluno` e `avaliacao` são
    read-only — o vínculo é imutável depois de criada.

    `aluno_nome` poupa o frontend de carregar a turma toda só pra
    mostrar quem é quem na tela de lançamento.

    `ultima_edicao` (com `por` e `em`) expõe o último snapshot do
    audit log — o Diniz pediu rastreabilidade visível porque qualquer
    professor da escola pode lançar/editar.
    """

    aluno_nome = serializers.CharField(
        source="aluno.nome_completo", read_only=True
    )
    aluno_matricula = serializers.CharField(
        source="aluno.matricula", read_only=True
    )
    ultima_edicao = serializers.SerializerMethodField()

    class Meta:
        model = NotaAvaliacao
        fields = [
            "id",
            "avaliacao",
            "aluno",
            "aluno_nome",
            "aluno_matricula",
            "nota",
            "observacao",
            "ultima_edicao",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = [
            "id",
            "avaliacao",
            "aluno",
            "aluno_nome",
            "aluno_matricula",
            "ultima_edicao",
            "criado_em",
            "atualizado_em",
        ]

    def get_ultima_edicao(self, obj: NotaAvaliacao) -> dict | None:
        """Devolve `{por, em}` do último snapshot do simple_history.

        Quando o histórico ainda não tem entrada (não devia acontecer,
        mas defensivo), retorna None. `por` é o `username` do usuário
        que disparou o save — capturado pelo `HistoryRequestMiddleware`.
        """
        ultimo = obj.history.first()
        if ultimo is None:
            return None
        user = getattr(ultimo, "history_user", None)
        return {
            "por": user.username if user else None,
            "em": ultimo.history_date.isoformat()
            if ultimo.history_date
            else None,
        }


class LancarNotaItemSerializer(serializers.Serializer):
    """Item de uma lista no payload do endpoint de lançamento em lote."""

    aluno_id = serializers.IntegerField()
    # `nota` pode ser null pra "deslançar" uma nota antes preenchida.
    nota = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        allow_null=True,
        required=False,
    )
    observacao = serializers.CharField(
        max_length=300, required=False, allow_blank=True
    )


class LancarNotasPayloadSerializer(serializers.Serializer):
    """Payload do `POST /avaliacoes/{id}/lancar-notas/`.

    Aceita lista parcial — só os alunos que mudaram. Cada item é
    processado dentro de uma transação atômica no endpoint pra evitar
    estado inconsistente em caso de falha no meio.
    """

    itens = LancarNotaItemSerializer(many=True)
