"""Views da app avaliacao."""
from django.db import transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from simple_history.utils import bulk_create_with_history, bulk_update_with_history

from apps.common.permissions import (
    IsAdminOrDiretor,
    IsAdminOrDiretorOrProfessor,
    IsAdminOrDiretorOrProfessorOrInspetor,
)
from apps.common.views import EscopoEscolaMixin, ReadWritePermissionMixin
from apps.escola.models import Aluno

from .models import Avaliacao, NotaAvaliacao, NotaPeriodo, PeriodoAvaliativo
from .serializers import (
    AvaliacaoSerializer,
    InicializarNotasPeriodoPayloadSerializer,
    LancarNotasFinaisPayloadSerializer,
    LancarNotasPayloadSerializer,
    NotaAvaliacaoSerializer,
    NotaPeriodoSerializer,
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

        # Coleta falhas e mutações antes de tocar no banco. Qualquer
        # aluno fora da avaliação invalida o lote inteiro — abortamos
        # sem abrir transação em vez de `set_rollback` (mais simples).
        falhas: list[dict] = []
        a_atualizar: list[NotaAvaliacao] = []
        agora = timezone.now()

        for item in itens:
            aluno_id = item["aluno_id"]
            nota_obj = notas_por_aluno.get(aluno_id)
            if nota_obj is None:
                falhas.append(
                    {
                        "aluno_id": aluno_id,
                        "motivo": "Aluno não pertence a esta avaliação.",
                    }
                )
                continue
            # `nota` pode ser None (deslançar). `observacao` cai pro
            # vazio se ausente — não deixamos None no banco pra manter
            # `blank=True` consistente.
            nota_obj.nota = item.get("nota", None)
            if "observacao" in item:
                nota_obj.observacao = item["observacao"] or ""
            # `bulk_update_with_history` não dispara `auto_now`, então
            # alimentamos `atualizado_em` manualmente.
            nota_obj.atualizado_em = agora
            a_atualizar.append(nota_obj)

        if falhas:
            return Response(
                {"atualizadas": 0, "falhas": falhas},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if a_atualizar:
            with transaction.atomic():
                # `bulk_update_with_history` preserva o audit log do
                # `simple_history` (snapshot por linha) e substitui um
                # `.save()` em loop que disparava N UPDATEs + N INSERTs
                # na tabela `historicalnotaavaliacao`.
                bulk_update_with_history(
                    a_atualizar,
                    NotaAvaliacao,
                    ["nota", "observacao", "atualizado_em"],
                )

        return Response(
            {"atualizadas": len(a_atualizar), "falhas": []},
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


# ===================================================================== #
# NotaPeriodo                                                            #
# ===================================================================== #


class NotaPeriodoViewSet(
    EscopoEscolaMixin,
    _AvaliacaoReadWriteMixin,
    viewsets.ReadOnlyModelViewSet,
):
    """Leitura + endpoints custom pra inicialização e lançamento em lote.

    CRUD direto é proibido (sem POST/PATCH/DELETE convencionais) — o
    ciclo de vida é controlado pelos endpoints:

    - `POST /inicializar/`: cria `NotaPeriodo(nota_final=NULL)` por
      aluno ativo da turma que ainda não tem pra aquele
      `(disciplina, periodo)`. Retorna a lista completa.
    - `POST /lancar-em-lote/`: UPSERT atômico das notas finais informadas.
    - `GET /{id}/historico/`: snapshots do `simple_history` (audit log).

    Filtros suportam `?turma=X&disciplina=Y&periodo=Z` pra listar a
    matriz daquela combinação.
    """

    queryset = (
        NotaPeriodo.objects.select_related(
            "aluno__turma", "disciplina", "periodo", "escola"
        )
        .order_by("aluno__nome_completo")
    )
    serializer_class = NotaPeriodoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["disciplina", "periodo", "aluno"]

    def get_queryset(self):
        """Adiciona filtro implícito por turma (via aluno__turma) em
        cima do escopo de escola do mixin."""
        qs = super().get_queryset()
        turma_id = self.request.query_params.get("turma")
        if turma_id:
            qs = qs.filter(aluno__turma_id=turma_id)
        return qs

    @action(detail=False, methods=["post"], url_path="inicializar")
    def inicializar(self, request):
        """`POST /notas-periodo/inicializar/` — auto-cria vazias.

        Recebe `{turma, disciplina, periodo}`. Pra cada aluno ativo da
        turma que NÃO tem `NotaPeriodo(disciplina, periodo)`, cria uma
        com `nota_final=NULL`. Aluno inativo é pulado (não faz sentido
        média de ex-aluno).

        Resposta: lista atualizada das notas (mesma forma da
        `/notas-periodo/?turma=X&disciplina=Y&periodo=Z`).
        """
        payload = InicializarNotasPeriodoPayloadSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        turma_id = payload.validated_data["turma"]
        disciplina_id = payload.validated_data["disciplina"]
        periodo_id = payload.validated_data["periodo"]

        # Valida que tudo pertence à escola do usuário (escopo).
        escola_id = self._resolver_escola_id(request, turma_id)
        if escola_id is None:
            return Response(
                {"detail": "Turma não encontrada ou fora do seu escopo."},
                status=status.HTTP_404_NOT_FOUND,
            )

        alunos_ativos_ids = Aluno.objects.filter(
            turma_id=turma_id, ativo=True
        ).values_list("id", flat=True)

        # Identifica quais já têm nota pra evitar UniqueViolation.
        existentes = set(
            NotaPeriodo.objects.filter(
                disciplina_id=disciplina_id,
                periodo_id=periodo_id,
                aluno_id__in=alunos_ativos_ids,
            ).values_list("aluno_id", flat=True)
        )

        faltantes = [aid for aid in alunos_ativos_ids if aid not in existentes]
        if faltantes:
            with transaction.atomic():
                NotaPeriodo.objects.bulk_create(
                    [
                        NotaPeriodo(
                            escola_id=escola_id,
                            aluno_id=aid,
                            disciplina_id=disciplina_id,
                            periodo_id=periodo_id,
                        )
                        for aid in faltantes
                    ]
                )

        # Devolve a lista completa pro frontend popular a tabela.
        qs = (
            NotaPeriodo.objects.filter(
                aluno_id__in=alunos_ativos_ids,
                disciplina_id=disciplina_id,
                periodo_id=periodo_id,
            )
            .select_related("aluno", "disciplina", "periodo")
            .order_by("aluno__nome_completo")
        )
        serialized = NotaPeriodoSerializer(qs, many=True).data
        return Response(serialized)

    @action(detail=False, methods=["post"], url_path="lancar-em-lote")
    def lancar_em_lote(self, request):
        """`POST /notas-periodo/lancar-em-lote/` — UPSERT atômico.

        Recebe `{turma, disciplina, periodo, itens: [...]}`. Pra cada
        item, cria ou atualiza a `NotaPeriodo` correspondente. Aluno
        que não pertence à turma falha o lote inteiro (rollback).

        Resposta `{atualizadas, falhas}` igual ao `lancar-notas` da
        Avaliação.
        """
        payload = LancarNotasFinaisPayloadSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        turma_id = payload.validated_data["turma"]
        disciplina_id = payload.validated_data["disciplina"]
        periodo_id = payload.validated_data["periodo"]
        itens = payload.validated_data["itens"]

        escola_id = self._resolver_escola_id(request, turma_id)
        if escola_id is None:
            return Response(
                {"detail": "Turma não encontrada ou fora do seu escopo."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Cache de alunos da turma pra validar que cada `aluno_id` do
        # payload pertence à turma alvo — bloqueio defensivo.
        alunos_da_turma = set(
            Aluno.objects.filter(turma_id=turma_id).values_list(
                "id", flat=True
            )
        )

        # Indexa as NotaPeriodo existentes por aluno_id em uma query só.
        # `in_bulk(field_name="aluno_id")` não serve aqui — exige
        # `unique=True` a nível de modelo, e a unicidade só vem do
        # composto (escola, aluno, disciplina, periodo).
        existentes_por_aluno = {
            n.aluno_id: n
            for n in NotaPeriodo.objects.filter(
                disciplina_id=disciplina_id,
                periodo_id=periodo_id,
                aluno_id__in=alunos_da_turma,
            )
        }

        # Coleta falhas e mutações antes de abrir transação — qualquer
        # aluno fora da turma invalida o lote inteiro.
        falhas: list[dict] = []
        a_criar: list[NotaPeriodo] = []
        a_atualizar: list[NotaPeriodo] = []
        agora = timezone.now()

        for item in itens:
            aluno_id = item["aluno_id"]
            if aluno_id not in alunos_da_turma:
                falhas.append(
                    {
                        "aluno_id": aluno_id,
                        "motivo": "Aluno não pertence à turma alvo.",
                    }
                )
                continue

            existente = existentes_por_aluno.get(aluno_id)
            if existente is not None:
                if "nota_final" in item:
                    existente.nota_final = item.get("nota_final")
                if "observacao" in item:
                    existente.observacao = item.get("observacao") or ""
                existente.atualizado_em = agora
                a_atualizar.append(existente)
            else:
                a_criar.append(
                    NotaPeriodo(
                        escola_id=escola_id,
                        aluno_id=aluno_id,
                        disciplina_id=disciplina_id,
                        periodo_id=periodo_id,
                        nota_final=item.get("nota_final"),
                        observacao=item.get("observacao") or "",
                    )
                )

        if falhas:
            return Response(
                {"atualizadas": 0, "falhas": falhas},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # `bulk_*_with_history` preservam o audit log do
            # `simple_history` e substituem o `get_or_create` em loop
            # que disparava até 2 queries por aluno (60 pra 30 alunos).
            #
            # `ignore_conflicts=True` no bulk_create cobre a race
            # condition de duas requests tentando criar
            # (escola, aluno, disciplina, periodo) ao mesmo tempo —
            # a perdedora não levanta IntegrityError, e fechamos a
            # corrida fazendo um UPDATE no segundo passe pros conflitos
            # reais detectados via releitura.
            if a_criar:
                bulk_create_with_history(
                    a_criar, NotaPeriodo, ignore_conflicts=True
                )
                # Releitura sob a transação: identifica quem ficou no
                # banco. Pode ser nosso INSERT bem-sucedido OU registro
                # de outra request que ganhou a corrida.
                intencao_por_aluno = {obj.aluno_id: obj for obj in a_criar}
                gravados = NotaPeriodo.objects.filter(
                    disciplina_id=disciplina_id,
                    periodo_id=periodo_id,
                    aluno_id__in=list(intencao_por_aluno),
                )
                for atual in gravados:
                    intencao = intencao_por_aluno.get(atual.aluno_id)
                    if intencao is None:
                        continue
                    if (
                        atual.nota_final == intencao.nota_final
                        and atual.observacao == intencao.observacao
                    ):
                        # Nosso INSERT vingou (ou a outra request gravou
                        # exatamente o mesmo valor) — nada pra atualizar.
                        continue
                    # Conflito real: outra request criou com valor
                    # diferente. Sobrescrevemos com nossa intenção pra
                    # preservar a semântica de UPSERT.
                    atual.nota_final = intencao.nota_final
                    atual.observacao = intencao.observacao
                    atual.atualizado_em = agora
                    a_atualizar.append(atual)

            if a_atualizar:
                bulk_update_with_history(
                    a_atualizar,
                    NotaPeriodo,
                    ["nota_final", "observacao", "atualizado_em"],
                )

        return Response(
            {"atualizadas": len(a_criar) + len(a_atualizar), "falhas": []},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="historico")
    def historico(self, request, pk=None):
        """`GET /notas-periodo/{id}/historico/` — audit log."""
        nota: NotaPeriodo = self.get_object()
        eventos = []
        for snapshot in nota.history.all():
            user = getattr(snapshot, "history_user", None)
            eventos.append(
                {
                    "nota_final": (
                        str(snapshot.nota_final)
                        if snapshot.nota_final is not None
                        else None
                    ),
                    "observacao": snapshot.observacao,
                    "por": user.username if user else None,
                    "em": snapshot.history_date.isoformat()
                    if snapshot.history_date
                    else None,
                    "tipo": snapshot.history_type,
                }
            )
        return Response({"eventos": eventos})

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _resolver_escola_id(self, request, turma_id: int) -> int | None:
        """Resolve a escola alvo do payload de lote/inicializar.

        Confirma que a turma existe e está no escopo do usuário (admin
        vê tudo; outros perfis só veem a própria escola). Retorna o
        `escola_id` da turma — usado pra criar/atualizar `NotaPeriodo`
        sem confiar no payload (que nem manda `escola`).
        """
        from apps.escola.models import Turma

        qs = Turma.objects.filter(pk=turma_id)
        user = request.user
        if (
            user.is_authenticated
            and not user.is_superuser
            and getattr(user, "perfil", None) != "admin"
        ):
            escola_user = getattr(user, "escola_id", None)
            if escola_user is None:
                return None
            qs = qs.filter(escola_id=escola_user)
        turma = qs.first()
        return turma.escola_id if turma else None
