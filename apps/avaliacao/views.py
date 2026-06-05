"""Views da app avaliacao."""
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.permissions import (
    IsAdminOrDiretor,
    IsAdminOrDiretorOrProfessor,
    IsAdminOrDiretorOrProfessorOrInspetor,
)
from apps.common.views import EscopoEscolaMixin, ReadWritePermissionMixin
from apps.escola.models import Aluno

from .models import Avaliacao, NotaAvaliacao, PeriodoAvaliativo
from .serializers import (
    AvaliacaoSerializer,
    LancarNotasPayloadSerializer,
    NotaAvaliacaoSerializer,
    PeriodoAvaliativoSerializer,
)


class _PeriodoAvaliativoReadWriteMixin(ReadWritePermissionMixin):
    """Leitura ampla (qualquer perfil que opera o sistema vê os períodos
    pra contextualizar avaliações/boletim). Escrita restrita a quem
    configura escola: admin/diretor/secretaria (`IsAdminOrDiretor`)."""

    READ_PERMISSION = IsAdminOrDiretorOrProfessorOrInspetor
    WRITE_PERMISSION = IsAdminOrDiretor


class PeriodoAvaliativoViewSet(
    EscopoEscolaMixin,
    _PeriodoAvaliativoReadWriteMixin,
    viewsets.ModelViewSet,
):
    """CRUD dos períodos avaliativos da escola.

    Escopo: queryset filtrado pela escola do JWT (admin global vê tudo).
    Soft delete via `ativo=False` no DELETE — preserva histórico de
    avaliações apontando pro período.
    """

    queryset = PeriodoAvaliativo.objects.select_related("escola").order_by(
        "-ano_letivo", "ordem"
    )
    serializer_class = PeriodoAvaliativoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["ano_letivo", "ativo"]

    def perform_destroy(self, instance: PeriodoAvaliativo) -> None:
        """Soft delete: marca `ativo=False`. Mantém o registro no banco
        pra preservar histórico de avaliações futuras que apontem pra ele."""
        instance.ativo = False
        instance.save(update_fields=["ativo", "atualizado_em"])


# ===================================================================== #
# Avaliacao + NotaAvaliacao                                              #
# ===================================================================== #


class _AvaliacaoReadWriteMixin(ReadWritePermissionMixin):
    """Leitura ampla (inspetor inclui pra acompanhamento). Escrita pra
    qualquer professor da escola — decisão consciente do Diniz: 'deixa
    como qualquer um, assim as pessoas se ajudam quando necessário'. O
    audit log do `simple_history` garante a rastreabilidade."""

    READ_PERMISSION = IsAdminOrDiretorOrProfessorOrInspetor
    WRITE_PERMISSION = IsAdminOrDiretorOrProfessor


class AvaliacaoViewSet(
    EscopoEscolaMixin,
    _AvaliacaoReadWriteMixin,
    viewsets.ModelViewSet,
):
    """CRUD de avaliações + lançamento em lote de notas.

    `perform_create` auto-gera uma `NotaAvaliacao(nota=NULL)` por aluno
    ativo da turma — assim o professor já abre a tela pronta pra lançar
    sem precisar adicionar aluno por aluno.

    Soft delete via `ativo=False`.
    """

    queryset = (
        Avaliacao.objects.select_related(
            "turma", "disciplina", "professor", "periodo", "escola"
        )
        .order_by("-data", "-criado_em")
    )
    serializer_class = AvaliacaoSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = [
        "turma",
        "disciplina",
        "professor",
        "periodo",
        "tipo",
        "ativo",
    ]
    search_fields = ["titulo", "descricao"]

    def perform_create(self, serializer) -> None:
        """Cria a Avaliacao e auto-popula NotaAvaliacao por aluno ativo
        da turma — espelhando o padrão de Presença → ItemPresenca.

        Usa `transaction.atomic` pra que o conjunto Avaliacao+notas
        seja salvo como unidade. Aluno inativo é pulado (não faz sentido
        lançar nota pra ex-aluno).
        """
        with transaction.atomic():
            avaliacao: Avaliacao = serializer.save()
            alunos_ativos = Aluno.objects.filter(
                turma=avaliacao.turma, ativo=True
            ).values_list("id", flat=True)
            NotaAvaliacao.objects.bulk_create(
                [
                    NotaAvaliacao(
                        avaliacao=avaliacao,
                        aluno_id=aluno_id,
                        escola_id=avaliacao.escola_id,
                    )
                    for aluno_id in alunos_ativos
                ]
            )

    def perform_destroy(self, instance: Avaliacao) -> None:
        instance.ativo = False
        instance.save(update_fields=["ativo", "atualizado_em"])

    @action(detail=True, methods=["post"], url_path="lancar-notas")
    def lancar_notas(self, request, pk=None):
        """`POST /avaliacoes/{id}/lancar-notas/` — payload em lote.

        Aceita `{itens: [{aluno_id, nota, observacao?}]}`. Atualiza só
        os alunos da lista, deixando os demais intactos. Tudo numa
        transação — se algum aluno não pertence à avaliação ou outra
        validação falhar, **nada é salvo**.

        Resposta: `{atualizadas: N, falhas: [{aluno_id, motivo}]}`.
        """
        avaliacao: Avaliacao = self.get_object()
        payload = LancarNotasPayloadSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        itens = payload.validated_data["itens"]

        # Index das NotaAvaliacao existentes — evita N+1 e permite
        # detectar aluno fora da avaliação.
        notas_por_aluno = {
            n.aluno_id: n
            for n in NotaAvaliacao.objects.filter(avaliacao=avaliacao)
        }

        falhas: list[dict] = []
        atualizadas = 0
        with transaction.atomic():
            for item in itens:
                aluno_id = item["aluno_id"]
                nota_obj = notas_por_aluno.get(aluno_id)
                if nota_obj is None:
                    falhas.append(
                        {
                            "aluno_id": aluno_id,
                            "motivo": (
                                "Aluno não pertence a esta avaliação."
                            ),
                        }
                    )
                    continue
                # `nota` pode ser None (deslançar). `observacao` cai
                # pro vazio se ausente — não deixamos `None` no banco
                # pra manter `blank=True` consistente.
                nota_obj.nota = item.get("nota", None)
                if "observacao" in item:
                    nota_obj.observacao = item["observacao"] or ""
                nota_obj.save(
                    update_fields=["nota", "observacao", "atualizado_em"]
                )
                atualizadas += 1

            if falhas:
                # Rollback explícito: qualquer falha invalida o lote
                # inteiro pra evitar estado parcial.
                transaction.set_rollback(True)
                return Response(
                    {"atualizadas": 0, "falhas": falhas},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(
            {"atualizadas": atualizadas, "falhas": []},
            status=status.HTTP_200_OK,
        )


class NotaAvaliacaoViewSet(
    EscopoEscolaMixin,
    _AvaliacaoReadWriteMixin,
    viewsets.ReadOnlyModelViewSet,
):
    """Leitura + histórico das notas individuais.

    Usamos `ReadOnlyModelViewSet` (sem create/update/delete) porque o
    ciclo de vida das notas é controlado pela `AvaliacaoViewSet` —
    auto-geradas na criação da Avaliação e atualizadas via endpoint
    dedicado `lancar-notas`. Acessar `/notas-avaliacao/` é útil pra
    inspeção, filtros por aluno e leitura do histórico.
    """

    queryset = (
        NotaAvaliacao.objects.select_related(
            "aluno", "avaliacao__turma", "avaliacao__disciplina", "escola"
        )
        .order_by("aluno__nome_completo")
    )
    serializer_class = NotaAvaliacaoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["avaliacao", "aluno"]

    @action(detail=True, methods=["get"], url_path="historico")
    def historico(self, request, pk=None):
        """`GET /notas-avaliacao/{id}/historico/` — snapshots do simple_history.

        Devolve a sequência de mudanças (mais recente primeiro) com
        `nota`, `observacao`, `por` (username) e `em` (timestamp). Pra
        suportar tela de "quem mudou X pra Y, quando".
        """
        nota: NotaAvaliacao = self.get_object()
        eventos = []
        for snapshot in nota.history.all():
            user = getattr(snapshot, "history_user", None)
            eventos.append(
                {
                    "nota": (
                        str(snapshot.nota)
                        if snapshot.nota is not None
                        else None
                    ),
                    "observacao": snapshot.observacao,
                    "por": user.username if user else None,
                    "em": snapshot.history_date.isoformat()
                    if snapshot.history_date
                    else None,
                    "tipo": snapshot.history_type,  # '+'/'~'/'-'
                }
            )
        return Response({"eventos": eventos})
