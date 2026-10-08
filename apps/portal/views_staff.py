"""Views do STAFF sobre os responsáveis (fatia 6b do `PORTAL.md`).

Separado de `views.py` de propósito: lá moram as views do **portal**, com
autenticação própria (`PortalJWTAuthentication`). Aqui é a área
administrativa, com a autenticação padrão do staff. Misturar as duas numa
casa só foi o que tornou a confusão de token possível de começo, e manter
a fronteira visível no nome do arquivo é barato.

A listagem alimenta a tela "Responsáveis", que é onde a secretaria dispara
o convite individual. O envio em si continua no
`ConvidarResponsavelView` (fatia 3), com rate limit próprio.

`ResponsavelAlunoStaffViewSet` é a escrita do vínculo (fatia 4 do
`RESPONSAVEIS.md`) — o que permite à secretaria cadastrar o segundo
responsável sem passar pelo `/admin/`.
"""
from django.db.models import Exists, OuterRef, Subquery
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from rest_framework import filters, mixins, viewsets
from rest_framework.exceptions import ValidationError

from apps.common.pagination import PaginacaoCompulsoria, PaginacaoPadrao
from apps.common.permissions import IsAdminOrDiretor
from apps.common.views import EscopoEscolaMixin, FiltroEscopoObrigatorioMixin

from .models import ConviteResponsavel, Responsavel, ResponsavelAluno
from .serializers import (
    ResponsavelAlunoStaffSerializer,
    ResponsavelStaffSerializer,
)

# Situações que o `?situacao=` aceita. São derivadas (senha utilizável +
# convite pendente), não um campo, então o filtro é resolvido aqui e não
# por `filterset_fields`.
SITUACOES_VALIDAS = frozenset(
    {"inativo", "ativo", "convidado", "convite_expirado", "sem_convite"}
)


class ResponsavelStaffViewSet(EscopoEscolaMixin, viewsets.ReadOnlyModelViewSet):
    """`GET /responsaveis/` e `/responsaveis/<id>/` — nível-diretor.

    Somente leitura. O cadastro de responsável nasce da semeadura
    (`portal_semear_responsaveis`) ou do admin; esta tela existe pra ver o
    estado do acesso e convidar, não pra criar conta de usuário externo
    pela API do staff.

    Mesma permissão do convite (`IsAdminOrDiretor`, que cobre secretaria e
    coordenador como aliases): quem pode convidar é quem pode ver a lista.
    """

    queryset = Responsavel.objects.all()
    serializer_class = ResponsavelStaffSerializer
    permission_classes = [IsAdminOrDiretor]
    # Cresce com a escola (um por responsável, centenas), então pagina por
    # default. A tela passa `?page`.
    pagination_class = PaginacaoCompulsoria
    filter_backends = [filters.SearchFilter]
    # Busca pelo nome do aluno também: a secretaria procura "o pai do
    # João", não o nome do responsável, que às vezes nem está preenchido.
    search_fields = ["nome", "email", "alunos__nome_completo"]

    def get_queryset(self):
        agora = timezone.now()
        pendentes = ConviteResponsavel.objects.filter(
            responsavel=OuterRef("pk"),
            usado_em__isnull=True,
            expira_em__gt=agora,
        ).order_by("-expira_em")

        qs = (
            super()
            .get_queryset()
            # `Exists`/`Subquery` em vez de consultar por linha: a situação
            # de cada conta sairia em 2 queries por responsável numa tela
            # de 20 linhas.
            .annotate(
                tem_convite_pendente=Exists(pendentes),
                convite_expira_em=Subquery(pendentes.values("expira_em")[:1]),
                tem_convite=Exists(
                    ConviteResponsavel.objects.filter(responsavel=OuterRef("pk"))
                ),
            )
            .prefetch_related("alunos__turma")
            .order_by("nome", "pk")
        )

        return qs

    def filter_queryset(self, queryset):
        """Aplica o `?situacao=` só na listagem.

        O DRF chama `filter_queryset` também no `retrieve`, por dentro do
        `get_object`. Com o filtro no `get_queryset`, como estava,
        `/responsaveis/<id>/?situacao=ativo` devolvia 404 pra um
        responsável que existe, e `?situacao=xpto` devolvia 400 numa rota
        de detalhe que não tem filtro nenhum — bastava alguém levar os
        filtros da tela pra URL do detalhe. É a mesma armadilha que
        `ComunicadoViewSet` já tinha pago; o remédio é o mesmo.

        As anotações continuam no `get_queryset`: o serializer precisa
        delas pra derivar a situação, inclusive no detalhe.
        """
        queryset = super().filter_queryset(queryset)
        if self.action != "list":
            return queryset

        situacao = self.request.query_params.get("situacao")
        if not situacao:
            return queryset
        if situacao not in SITUACOES_VALIDAS:
            raise ValidationError(
                {
                    "situacao": (
                        "Situação inválida. Use uma de: "
                        + ", ".join(sorted(SITUACOES_VALIDAS))
                    )
                }
            )
        return self._filtrar_situacao(queryset, situacao)

    def _filtrar_situacao(self, qs, situacao: str):
        """Traduz a situação derivada em filtro de queryset.

        `ativo` depende de ter senha utilizável, que no Django é "o hash
        não começa com `!`". Não há como expressar isso em ORM sem
        depender desse detalhe, então o filtro usa `password__startswith`
        — com o mesmo prefixo que `set_unusable_password` grava.
        """
        if situacao == "inativo":
            return qs.filter(ativo=False)

        qs = qs.filter(ativo=True)
        if situacao == "ativo":
            return qs.exclude(password__startswith="!").exclude(password="")
        # As três restantes são contas sem senha utilizável.
        sem_senha = qs.filter(password__startswith="!") | qs.filter(password="")
        if situacao == "convidado":
            return sem_senha.filter(tem_convite_pendente=True)
        if situacao == "convite_expirado":
            return sem_senha.filter(tem_convite_pendente=False, tem_convite=True)
        return sem_senha.filter(tem_convite=False)


class ResponsavelAlunoStaffViewSet(
    FiltroEscopoObrigatorioMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """`GET/POST /vinculos-responsavel/` e `DELETE /<id>/` — nível-diretor.

    É o endpoint que entrega a fatia 4: sem ele o vínculo só nasce no
    `/admin/`, e a capacidade de ter mãe e pai cadastrados — que as fatias
    1 a 3 já sustentam no envio de email — fica inalcançável pela
    secretaria.

    **Sem `PUT`/`PATCH` de propósito.** Um vínculo é um par; trocar o
    aluno ou o responsável é outro vínculo, não uma edição deste. Apagar e
    criar mantém o histórico auditado legível ("este vínculo existiu de tal
    data a tal data") em vez de um registro que muda de identidade.

    **`DELETE` apaga a linha de verdade**, divergindo do soft delete que o
    projeto prefere. É o que o `PORTAL.md` decidiu para este modelo:
    desvincular é ação explícita, não efeito colateral de desativar uma
    conta. O histórico não se perde porque o modelo é auditado — o
    `simple_history` grava a deleção.

    Consequência que a UI precisa dizer em voz alta: remover o **último**
    vínculo de um aluno não o silencia. Pelo `RESPONSAVEIS.md` §4.1, aluno
    com zero vínculos volta a receber email pelo `Aluno.email_responsavel`.
    """

    queryset = ResponsavelAluno.objects.all()
    serializer_class = ResponsavelAlunoStaffSerializer
    permission_classes = [IsAdminOrDiretor]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["responsavel", "aluno"]
    # A UI sempre pede os vínculos de UM responsável (ou de um aluno), e o
    # resultado é do tamanho de uma família. Paginar seria ruído; carregar
    # a escola inteira, desperdício. Mesma escolha dos endpoints matriz:
    # exigir escopo no `list` e não paginar por default.
    pagination_class = PaginacaoPadrao
    FILTROS_ESCOPO = ("responsavel", "aluno")

    def get_queryset(self):
        """Escopo por escola feito à mão — e pelos DOIS lados.

        Não usa `EscopoEscolaMixin` porque `ResponsavelAluno` não tem FK
        `escola`: a escola vem de `responsavel` e de `aluno`, que o
        `clean()` obriga a coincidir (uma terceira cópia da FK abriria
        espaço pra divergência, ver o model).

        Filtrar pelos dois lados é redundante **enquanto o invariante
        vale**, e é exatamente por isso que está aqui: `objects.create()`
        não passa por `clean()`, então um vínculo cruzado feito por shell
        existe em teoria — e aí filtrar só pelo responsável mostraria a
        um diretor o nome de um aluno de outra escola.
        """
        qs = super().get_queryset().select_related(
            "responsavel", "aluno", "aluno__turma"
        )
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if user.is_superuser or getattr(user, "perfil", None) == "admin":
            return qs
        escola_id = getattr(user, "escola_id", None)
        if not escola_id:
            return qs.none()
        return qs.filter(
            responsavel__escola_id=escola_id, aluno__escola_id=escola_id
        )
