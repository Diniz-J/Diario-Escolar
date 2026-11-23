"""Views da app presenca — CRUD de chamadas e itens individuais.

Padrão de permissão:
- Leitura (`list`, `retrieve`): admin/diretor/professor/inspetor.
- Escrita (`create`, `update`, `partial_update`, `destroy`): admin/diretor/professor.

Inspetor é incluído na leitura para que possa monitorar chamadas (ex.: cruzar
com ocorrências do dia) sem alterar os registros.

`RegistroPresencaViewSet.perform_create` gera automaticamente um `ItemPresenca`
com status=Presente para cada aluno ativo da turma, dentro de transação. Isso
materializa o caso de uso padrão: professor abre a chamada e só marca exceções.

`ItemPresencaViewSet` não expõe POST/DELETE — o ciclo de vida dos itens é
gerenciado pelo registro pai. Apenas GET e PATCH (mudar status/observação).
"""
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied

from apps.common.pagination import PaginacaoCompulsoria
from apps.common.permissions import (
    PERFIS_PRIVILEGIADOS,
    IsAdminOrDiretorOrProfessor,
    IsAdminOrDiretorOrProfessorOrInspetor,
    eh_admin_global,
)
from apps.common.views import (
    EscopoEscolaMixin,
    FiltroEscopoObrigatorioMixin,
    ReadWritePermissionMixin,
)

from .filters import RegistroPresencaFilter
from .models import ItemPresenca, RegistroPresenca
from .serializers import ItemPresencaSerializer, RegistroPresencaSerializer


def _eh_direcao(user) -> bool:
    return eh_admin_global(user) or getattr(user, "perfil", None) in PERFIS_PRIVILEGIADOS


def _professor_do_usuario(user):
    try:
        return user.professor
    except (AttributeError, ObjectDoesNotExist):
        return None


class _PresencaReadWriteMixin(ReadWritePermissionMixin):
    """Leitura inclui inspetor; escrita só admin/diretor/professor.

    Sobrescreve apenas READ_PERMISSION para incluir inspetor — escrita
    permanece com o default mais restritivo do mixin base, mas precisa
    de override explícito porque o default é `IsAdminOrDiretor` (sem
    professor).
    """

    READ_PERMISSION = IsAdminOrDiretorOrProfessorOrInspetor
    WRITE_PERMISSION = IsAdminOrDiretorOrProfessor


class RegistroPresencaViewSet(
    EscopoEscolaMixin, _PresencaReadWriteMixin, viewsets.ModelViewSet
):
    """CRUD de registros de presença. Cria itens automaticamente."""

    queryset = (
        RegistroPresenca.objects.select_related("turma", "professor", "escola")
        .order_by("-data")
    )
    serializer_class = RegistroPresencaSerializer
    # Histórico cresce sem teto (ano letivo × dias × turmas). Pagina por
    # default; dashboard/widgets pedem `?page_size=all`. `ItemPresenca`
    # NÃO recebe esse tratamento — escopo natural por chamada (~30 itens).
    pagination_class = PaginacaoCompulsoria
    filter_backends = [DjangoFilterBackend]
    filterset_class = RegistroPresencaFilter

    def _professor_do_registro(self, serializer) -> dict:
        """Resolve quem assina a chamada, no molde do diário de aula.

        O professor deixou de vir de um select: quem lança assina. A
        direção segue podendo abrir a chamada por outro (é ela que cobre
        falta e corrige lançamento), e o professor só por si mesmo — 403
        em vez de sobrescrever em silêncio, porque lançar presença em nome
        de outro é o que o registro existe pra impedir.

        Inspetor opera como professor mas não tem cadastro de `Professor`:
        a chamada dele fica sem assinatura, como antes.
        """
        user = self.request.user
        pedido = serializer.validated_data.get("professor")
        if _eh_direcao(user):
            return {}
        meu = _professor_do_usuario(user)
        if pedido is not None and meu is not None and pedido.pk != meu.pk:
            raise PermissionDenied(
                "Você só pode lançar chamada no seu próprio nome."
            )
        if meu is None:
            return {}
        return {"professor": meu}

    def perform_update(self, serializer) -> None:
        """Trava `professor` e `tempos` fora da direção.

        Sem isso, um professor comum poderia PATCH `professor=outro` e
        assinar por cima da chamada alheia, ou PATCH `tempos=[1,2,3]` num
        registro antigo e inflar silenciosamente a carga horária histórica
        — a régua da frequência pesa por `len(tempos)`, então o percentual
        do boletim mudaria sem rastro na UI. Direção segue podendo corrigir
        (é ela que cobre falta e normaliza lançamento errado).
        """
        if not _eh_direcao(self.request.user):
            mudou_professor = (
                "professor" in serializer.validated_data
                and serializer.validated_data["professor"] is not None
                and serializer.validated_data["professor"].pk
                != serializer.instance.professor_id
            )
            mudou_tempos = (
                "tempos" in serializer.validated_data
                and list(serializer.validated_data["tempos"])
                != list(serializer.instance.tempos or [])
            )
            if mudou_professor or mudou_tempos:
                raise PermissionDenied(
                    "Apenas a direção pode alterar o professor ou os tempos "
                    "de um registro já lançado."
                )
        serializer.save()

    def perform_create(self, serializer) -> None:
        """Cria o registro e popula `ItemPresenca` para cada aluno ativo.

        Tudo dentro de uma transação atômica: se a criação dos itens
        falhar, o próprio registro é revertido — evita ficar com registro
        sem itens em produção.

        Aluno inativo não recebe item: o padrão de diário escolar é que
        inativos saíram da turma e não devem aparecer na chamada. Se o
        aluno for reativado depois, novos registros já vão incluí-lo;
        registros antigos seguem sem ele (snapshot histórico).
        """
        professor = self._professor_do_registro(serializer)
        with transaction.atomic():
            registro = serializer.save(**professor)
            alunos_ativos = list(registro.turma.alunos.filter(ativo=True))
            # `bulk_create` não chama `save()` nem `clean()` — a invariante
            # `aluno.turma == registro.turma` já é garantida pelo filtro
            # acima, mas explicitar protege contra alterações futuras no
            # queryset que possam introduzir alunos de outra turma.
            for aluno in alunos_ativos:
                if aluno.turma_id != registro.turma_id:
                    raise ValueError(
                        f"Aluno {aluno.id} tem turma_id={aluno.turma_id} "
                        f"divergente de registro.turma_id={registro.turma_id}."
                    )
            ItemPresenca.objects.bulk_create(
                [
                    ItemPresenca(
                        registro=registro,
                        aluno=aluno,
                        status=ItemPresenca.Status.PRESENTE,
                        escola=registro.escola,
                    )
                    for aluno in alunos_ativos
                ]
            )


class ItemPresencaViewSet(
    FiltroEscopoObrigatorioMixin,
    EscopoEscolaMixin,
    _PresencaReadWriteMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Listagem e edição (PATCH/PUT) de itens individuais.

    Sem POST/DELETE de propósito: itens são criados pelo registro pai e
    removidos via cascade quando o registro é apagado.
    """

    # `list` exige escopo (a UI sempre passa ?registro=); sem isso seria
    # 1 linha por (aluno × chamada) da escola inteira.
    FILTROS_ESCOPO = ("registro", "aluno")

    queryset = (
        ItemPresenca.objects.select_related("registro", "aluno", "escola")
        .order_by("aluno__nome_completo")
    )
    serializer_class = ItemPresencaSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["registro", "aluno", "status"]
