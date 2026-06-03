"""Paginação padrão da API.

Estratégia:
- **Default = sem paginação** (retorna array direto). Mantém compatibilidade
  com chamadas que esperam o formato antigo (dashboards, agregações,
  formulários que populam selects).
- **Opt-in via `?page=N`** (ou `?page_size=N`): retorna o envelope DRF
  padrão `{count, next, previous, results}`. Listagens administrativas
  com muitos registros entram nesse modo.

Isso evita refatorar todos os hooks do frontend de uma vez — quem precisa
de paginação migra explicitamente, e quem agrega/popula select continua
puxando tudo numa request.
"""
from rest_framework.pagination import PageNumberPagination


class PaginacaoPadrao(PageNumberPagination):
    """20 itens/página por default; o cliente pode pedir até 100.

    `paginate_queryset` retorna `None` quando NEM `page` NEM `page_size`
    vierem nos query params — o DRF interpreta como "não paginar" e
    devolve a lista crua. Isso preserva o comportamento antigo da API
    pra consumidores que não foram migrados.
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
