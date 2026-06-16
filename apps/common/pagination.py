"""Paginação da API.

Duas classes pra cobrir os dois cenários do projeto:

- **`PaginacaoPadrao` (opt-in)**: só pagina com `?page` ou `?page_size`
  explícito. Default histórico — endpoints que servem dashboards,
  agregações e formulários (populam selects) usam essa classe pra não
  quebrar consumidores que esperam array cru.
- **`PaginacaoCompulsoria` (opt-out)**: pagina sempre, exceto com
  `?page_size=all`. Pra listagens administrativas que crescem sem teto
  (histórico de ocorrências, presença etc.) — quem precisa da lista
  inteira pede explicitamente.

Default `page_size=20`, máximo 100 nas duas classes — a única diferença
é o comportamento quando o cliente não passa nada.
"""
from rest_framework.pagination import PageNumberPagination


class PaginacaoPadrao(PageNumberPagination):
    """Opt-in: paginate apenas com sinal explícito do cliente.

    `paginate_queryset` retorna `None` quando NEM `page` NEM `page_size`
    vierem nos query params — o DRF interpreta como "não paginar" e
    devolve a lista crua. Preserva o comportamento antigo da API pra
    consumidores que não foram migrados.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        if (
            "page" not in request.query_params
            and self.page_size_query_param not in request.query_params
        ):
            # Sem sinal explícito de paginação — devolve tudo.
            return None
        return super().paginate_queryset(queryset, request, view=view)


class PaginacaoCompulsoria(PageNumberPagination):
    """Opt-out: paginate sempre, salvo `?page_size=all`.

    Usada nos endpoints que listam histórico volumoso — `OcorrenciaViewSet`
    e `RegistroPresencaViewSet`. Cliente que precisa da lista inteira
    (dashboards, exports) passa `?page_size=all` e recebe array cru.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        # `all` é o opt-out reservado — DRF não aceitaria como int.
        if request.query_params.get(self.page_size_query_param) == "all":
            return None
        return super().paginate_queryset(queryset, request, view=view)
