"""Filtros declarativos da app comunicados."""
import django_filters

from .models import Comunicado


class ComunicadoFilter(django_filters.FilterSet):
    # Range por data de criação: a listagem oferece "comunicados do mês".
    # Usa `criado_em` (não `enviado_em`) porque rascunho ainda não tem
    # data de envio e desapareceria do filtro.
    data_inicio = django_filters.DateFilter(
        field_name="criado_em", lookup_expr="date__gte"
    )
    data_fim = django_filters.DateFilter(
        field_name="criado_em", lookup_expr="date__lte"
    )
    # `?turma=3` responde "quais comunicados foram endereçados a esta
    # turma" — só pega os de destino `turmas` (os de escola inteira não
    # têm M2M preenchida, por design; ver ComunicadoSerializer.validate).
    turma = django_filters.NumberFilter(field_name="turmas__id")

    class Meta:
        model = Comunicado
        fields = ["status", "destino"]
