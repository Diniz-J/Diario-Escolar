"""Views do STAFF sobre os responsáveis (fatia 6b do `PORTAL.md`).

Separado de `views.py` de propósito: lá moram as views do **portal**, com
autenticação própria (`PortalJWTAuthentication`). Aqui é a área
administrativa, com a autenticação padrão do staff. Misturar as duas numa
casa só foi o que tornou a confusão de token possível de começo, e manter
a fronteira visível no nome do arquivo é barato.

A listagem alimenta a tela "Responsáveis", que é onde a secretaria dispara
o convite individual. O envio em si continua no
`ConvidarResponsavelView` (fatia 3), com rate limit próprio.
"""
from django.db.models import Exists, OuterRef, Subquery
from django.utils import timezone
from rest_framework import filters, viewsets
from rest_framework.exceptions import ValidationError

from apps.common.pagination import PaginacaoCompulsoria
from apps.common.permissions import IsAdminOrDiretor
from apps.common.views import EscopoEscolaMixin

from .models import ConviteResponsavel, Responsavel
from .serializers import ResponsavelStaffSerializer

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
