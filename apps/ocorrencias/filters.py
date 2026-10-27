"""Filtros declarativos da app ocorrencias.

Substitui o `filterset_fields` simples por um `FilterSet` explícito para
suportar range de datas (`data_inicio` / `data_fim`) sobre o campo
`data_ocorrencia` e **status repetível**, mantendo os filtros exatos por
turma/aluno/professor.
"""
import django_filters

from .models import Ocorrencia


class OcorrenciaFilter(django_filters.FilterSet):
    # Range de período: ambos opcionais e inclusivos.
    # `?data_inicio=2026-05-01&data_fim=2026-05-31` → ocorrências do mês.
    data_inicio = django_filters.DateFilter(
        field_name="data_ocorrencia", lookup_expr="gte"
    )
    data_fim = django_filters.DateFilter(
        field_name="data_ocorrencia", lookup_expr="lte"
    )

    # Repetível e somado em OU: `?status=aberta&status=em_andamento` é "o
    # que ainda está em aberto", que é a pergunta real da direção — e que
    # com um status por vez exigia duas consultas e duas folhas impressas.
    #
    # Declarado aqui em vez de ficar no `Meta.fields`, que geraria um
    # `ChoiceFilter` de igualdade exata. Um valor só continua funcionando,
    # então o front atual, o export e qualquer link salvo seguem válidos.
    #
    # `distinct=False` porque o filtro é sobre coluna da própria tabela:
    # não há JOIN pra multiplicar linha, e o `DISTINCT` que o
    # `MultipleChoiceFilter` aplica por default sairia caro de graça numa
    # listagem paginada.
    status = django_filters.MultipleChoiceFilter(
        choices=Ocorrencia.Status.choices, distinct=False
    )

    class Meta:
        model = Ocorrencia
        fields = ["status", "turma", "aluno", "professor"]
