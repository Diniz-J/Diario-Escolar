"""Views da app comunicados — CRUD de rascunho + disparo explícito.

Permissão (via `ReadWritePermissionMixin`, defaults do projeto):

- **Leitura** (`list`, `retrieve`, e as actions de consulta): nível-diretor
  + professor/inspetor. O corpo docente acompanha o que a escola comunicou
  aos pais, mas não publica.
- **Escrita** (criar, editar, excluir e `enviar`): só nível-diretor
  (admin/diretor/secretaria/coordenador). Disparar email pra todos os
  responsáveis é ato institucional.

O `enviar` cai no ramo de escrita porque o mixin devolve `WRITE_PERMISSION`
para toda ação que não seja `list`/`retrieve` — incluindo actions custom.
As actions de consulta (`previa`, `destinatarios`) precisam override
explícito, senão ficariam restritas a nível-diretor sem necessidade.
"""
import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.common.pagination import PaginacaoCompulsoria
from apps.common.views import EscopoEscolaMixin, ReadWritePermissionMixin

from .filters import ComunicadoFilter
from .models import Comunicado, ComunicadoDestinatario
from .serializers import (
    ComunicadoDestinatarioSerializer,
    ComunicadoSerializer,
)
from .services import contar_previa, enviar_comunicado

logger = logging.getLogger(__name__)

# Actions custom que são consulta, não escrita — herdam a permissão de
# leitura em vez da de escrita.
_ACTIONS_LEITURA = frozenset({"previa", "destinatarios"})


class ComunicadoViewSet(
    EscopoEscolaMixin, ReadWritePermissionMixin, viewsets.ModelViewSet
):
    """Comunicados aos responsáveis.

    Salvar cria/edita **rascunho** — nunca envia. O disparo é
    `POST /comunicados/{id}/enviar/`, e depois dele o comunicado fica
    imutável (registro do que chegou aos pais).
    """

    queryset = (
        Comunicado.objects.select_related("escola", "criado_por", "enviado_por")
        .prefetch_related("turmas")
        .order_by("-criado_em")
    )
    serializer_class = ComunicadoSerializer
    # Cresce sem teto (escola operando ano a ano); pagina por default.
    pagination_class = PaginacaoCompulsoria
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = ComunicadoFilter
    search_fields = ["titulo", "mensagem"]

    def get_permissions(self):
        if self.action in _ACTIONS_LEITURA:
            return [self.READ_PERMISSION()]
        return super().get_permissions()

    def filter_queryset(self, queryset):
        """Aplica os filtros de query string **somente** no `list`.

        `GenericAPIView.get_object()` chama `filter_queryset`, então sem
        este override os query params de uma action de detalhe seriam
        validados contra o `ComunicadoFilter`. Caso concreto que isso
        quebrava: `GET /comunicados/{id}/destinatarios/?status=sem_email`
        devolvia 400, porque `sem_email` é status de *destinatário* e o
        filtro da viewset o comparava com os status de *comunicado*
        (rascunho/enviando/enviado/falhou).

        Filtrar um lookup de objeto único não tem semântica útil de
        qualquer forma — o escopo por escola, que é o que importa pra
        segurança, vem do `EscopoEscolaMixin.get_queryset()` e segue
        valendo aqui.
        """
        if self.action != "list":
            return queryset
        return super().filter_queryset(queryset)

    def perform_create(self, serializer) -> None:
        """Registra a autoria. O comunicado nasce rascunho (default do model)."""
        usuario = self.request.user
        serializer.save(criado_por=usuario if usuario.is_authenticated else None)

    def perform_destroy(self, instance) -> None:
        """Só rascunho pode ser excluído.

        Comunicado disparado é histórico: apagá-lo sumiria com a prova do
        que foi enviado aos responsáveis (e com o log de entrega junto,
        via CASCADE).
        """
        if not instance.editavel:
            raise ValidationError(
                {
                    "detail": (
                        "Este comunicado já foi disparado e não pode ser "
                        "excluído."
                    )
                }
            )
        instance.delete()

    @action(detail=True, methods=["get"])
    def previa(self, request, pk=None):
        """Alcance do comunicado sem enviar nada.

        Alimenta o diálogo de confirmação do front: quantos responsáveis
        serão atingidos, quantas mensagens o provedor vai receber (após
        dedup de irmãos) e quantos alunos estão sem email cadastrado.
        """
        comunicado = self.get_object()
        return Response(contar_previa(comunicado))

    @action(detail=True, methods=["post"])
    def enviar(self, request, pk=None):
        """Dispara o comunicado para os responsáveis.

        Idempotente por status: só funciona a partir de `rascunho`. Um
        segundo clique (ou dois cliques simultâneos) recebe 409 em vez de
        enviar o lote de novo — email duplicado pra escola inteira não tem
        desfazer.

        Responde 202 (Accepted), não 200: em produção o envio continua em
        background depois da resposta. O front acompanha pelo status e
        pelos contadores.
        """
        comunicado = self.get_object()
        disparou = enviar_comunicado(comunicado, usuario=request.user)
        if not disparou:
            return Response(
                {
                    "detail": (
                        "Este comunicado não está em rascunho — o envio já "
                        "foi iniciado ou concluído."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        comunicado.refresh_from_db()
        serializer = self.get_serializer(comunicado)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"])
    def destinatarios(self, request, pk=None):
        """Log de entrega por aluno.

        Aceita `?status=falhou` (ou `enviado`/`sem_email`/`pendente`) pra
        responder direto "quem não recebeu". Não paginado: o teto natural
        é o número de alunos do público, e a tela precisa da lista inteira
        pra exportar/conferir.
        """
        comunicado = self.get_object()
        qs = comunicado.destinatarios.select_related("aluno", "aluno__turma")

        filtro_status = request.query_params.get("status")
        if filtro_status:
            validos = {c for c, _ in ComunicadoDestinatario.Status.choices}
            if filtro_status not in validos:
                raise ValidationError(
                    {
                        "status": (
                            "Status inválido. Use um de: "
                            + ", ".join(sorted(validos))
                        )
                    }
                )
            qs = qs.filter(status=filtro_status)

        serializer = ComunicadoDestinatarioSerializer(qs, many=True)
        return Response(serializer.data)
