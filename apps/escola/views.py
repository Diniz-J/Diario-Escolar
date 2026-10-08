"""Views da app escola — API REST com permissões granulares por ação.

Todos os ViewSets escopam o queryset à escola do `request.user` (via
`EscopoEscolaMixin` ou override manual em `EscolaViewSet`). Admin e superuser
bypassam o filtro.
"""
from django.template.loader import render_to_string
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError

from apps.common.import_export_views import ImportExportViewSetMixin
from apps.common.pdf import caminho_logo, render_pdf
from apps.common.permissions import IsAdmin, IsAdminOrDiretor
from apps.common.views import EscopoEscolaMixin, ReadWritePermissionMixin
from apps.relatorios.exportacao import (
    FORMATOS_PLANILHA,
    exportar_planilha,
    resolver_formato,
    resposta_download,
)
from apps.relatorios.services import (
    LIMITE_PDF_ALUNOS,
    agrupar_alunos_por_turma,
    linhas_alunos,
)

from .models import Aluno, Disciplina, Escola, Lecionamento, Professor, Turma
from .resources import (
    AlunoResource,
    DisciplinaResource,
    LecionamentoResource,
    ProfessorResource,
    TurmaResource,
)
from .serializers import (
    AlunoSerializer,
    DisciplinaSerializer,
    EscolaSerializer,
    LecionamentoSerializer,
    ProfessorSerializer,
    TurmaSerializer,
)

# Alias module-level: o render mora em `apps/common/pdf.py`, mas o nome
# fica aqui porque os testes dão `mock.patch` em
# `apps.escola.views._render_pdf`.
_render_pdf = render_pdf

FORMATOS_EXPORT = ("pdf", *FORMATOS_PLANILHA)


class EscolaViewSet(ReadWritePermissionMixin, viewsets.ModelViewSet):
    """CRUD de escolas. Apenas admins criam/editam/removem.

    Filtro de queryset é feito manualmente porque Escola é o tenant root —
    não tem FK `escola`, então não pode usar `EscopoEscolaMixin`.
    """

    queryset = Escola.objects.all().order_by("nome")
    serializer_class = EscolaSerializer
    filter_backends = [DjangoFilterBackend]
    # `importacao_em_lote_habilitada` é o filtro que a tela /import usa
    # pra listar só as escolas elegíveis ao pacote contratado.
    filterset_fields = ["ativa", "importacao_em_lote_habilitada"]
    READ_PERMISSION = IsAdminOrDiretor
    WRITE_PERMISSION = IsAdmin

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if user.is_superuser or getattr(user, "perfil", None) == "admin":
            return qs
        if not getattr(user, "escola_id", None):
            return qs.none()
        return qs.filter(id=user.escola_id)


class TurmaViewSet(
    ImportExportViewSetMixin,
    EscopoEscolaMixin,
    ReadWritePermissionMixin,
    viewsets.ModelViewSet,
):
    queryset = Turma.objects.select_related("escola").order_by("-ano_letivo", "nome")
    serializer_class = TurmaSerializer
    filter_backends = [DjangoFilterBackend]
    # `escola` removido: o queryset já é escopado por `EscopoEscolaMixin`.
    filterset_fields = ["ano_letivo", "turno", "ativa"]
    import_export_resource = TurmaResource
    import_export_nome_arquivo = "turmas"


class DisciplinaViewSet(
    ImportExportViewSetMixin,
    EscopoEscolaMixin,
    ReadWritePermissionMixin,
    viewsets.ModelViewSet,
):
    queryset = Disciplina.objects.select_related("escola").order_by("nome")
    serializer_class = DisciplinaSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["ativa"]
    import_export_resource = DisciplinaResource
    import_export_nome_arquivo = "disciplinas"


class AlunoViewSet(
    ImportExportViewSetMixin,
    EscopoEscolaMixin,
    ReadWritePermissionMixin,
    viewsets.ModelViewSet,
):
    """CRUD de alunos. Suporta busca por nome/matrícula e filtro por turma.

    DELETE faz soft delete (marca `ativo=False`). Decisão consciente para
    preservar histórico de ocorrências e registros de presença vinculados
    ao aluno — alunos com dados históricos não podem ser apagados de fato
    pela FK PROTECT, e o registro escolar tem valor de auditoria.

    Frontend que quiser esconder inativos da listagem usa `?ativo=true`
    via DjangoFilterBackend (filterset_fields já inclui `ativo`).
    """

    queryset = Aluno.objects.select_related("turma", "escola").order_by("nome_completo")
    serializer_class = AlunoSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["turma", "ativo"]
    search_fields = ["nome_completo", "matricula"]
    import_export_resource = AlunoResource
    import_export_nome_arquivo = "alunos"

    def perform_destroy(self, instance: Aluno) -> None:
        """Soft delete: só marca `ativo=False`, mantém a linha no banco."""
        instance.ativo = False
        instance.save(update_fields=["ativo", "atualizado_em"])

    @action(detail=False, methods=["get"])
    def relatorio(self, request):
        """`GET /alunos/relatorio/?formato=pdf|csv|xlsx` — cadastral.

        Deliberadamente SEPARADO do `export/` que o
        `ImportExportViewSetMixin` expõe. Aquele é o serviço de migração
        em massa: admin global, atrás do flag comercial
        `Escola.importacao_em_lote_habilitada`, e devolve a base no
        formato de reimportação. Este é a lista que a secretaria tira da
        própria escola pra usar no dia a dia — baixar a lista da sua
        turma não é a mesma coisa que extrair a base inteira.

        A permissão vem do `ReadWritePermissionMixin`: por não ser
        `list`/`retrieve`, cai no `WRITE_PERMISSION` (admin/diretor, com
        secretaria e coordenador como aliases). Professor não entra — a
        planilha leva nome e email de responsável. Há teste fixando os
        dois lados, porque a regra é consequência do mixin e não de uma
        declaração local: `permission_classes` no `@action` seria
        ignorado em silêncio, já que o mixin sobrescreve
        `get_permissions`.

        Reaproveita `get_queryset` (escopo de escola) e
        `filter_queryset` (`?turma=`, `?ativo=`, busca por nome e
        matrícula), então o arquivo sai com o mesmo recorte da tela.
        """
        formato = resolver_formato(request, FORMATOS_EXPORT, default="pdf")
        alunos = list(self.filter_queryset(self.get_queryset()))

        stem = "alunos"
        if formato in FORMATOS_PLANILHA:
            headers, linhas = linhas_alunos(alunos)
            return exportar_planilha(
                headers, linhas, formato=formato, stem=stem
            )

        if len(alunos) > LIMITE_PDF_ALUNOS:
            raise ValidationError(
                {
                    "detail": (
                        f"O recorte tem {len(alunos)} alunos e o PDF "
                        f"comporta {LIMITE_PDF_ALUNOS}. Filtre por turma "
                        "ou baixe em CSV/XLSX, que não têm esse limite."
                    )
                }
            )

        escola_usuario = getattr(request.user, "escola", None)
        contexto = {
            "grupos": agrupar_alunos_por_turma(alunos),
            "total": len(alunos),
            "escola_nome": (
                alunos[0].escola.nome
                if alunos
                else (escola_usuario.nome if escola_usuario else "")
            ),
            "recorte": self._descrever_recorte(request, alunos),
            "gerado_em": timezone.localtime(),
            "logo_path": caminho_logo(),
        }
        html_str = render_to_string("relatorio_alunos_pdf.html", contexto)
        return resposta_download(
            _render_pdf(html_str),
            content_type="application/pdf",
            nome_arquivo=f"{stem}.pdf",
        )

    def _descrever_recorte(self, request, alunos) -> str:
        """Rótulo legível do recorte, pro cabeçalho do PDF.

        O nome da turma sai dos alunos encontrados, não do `?turma=`
        recebido: o queryset é escopado, então um id de outra escola
        devolve lista vazia — mas resolver pelo parâmetro imprimiria o
        nome da turma alheia no cabeçalho.
        """
        partes = []
        if request.query_params.get("turma"):
            nomes = {aluno.turma.nome for aluno in alunos}
            if len(nomes) == 1:
                partes.append(f"turma {nomes.pop()}")

        ativo = request.query_params.get("ativo")
        if ativo is not None:
            ligado = ativo.lower() in ("true", "1")
            partes.append("ativos" if ligado else "inativos")

        busca = request.query_params.get("search")
        if busca:
            partes.append(f'busca "{busca}"')

        return " · ".join(partes) if partes else "Todos os alunos"

    def get_import_extras(self, request) -> dict:
        """Aceita `turno_padrao` e `ano_letivo_padrao` no upload.

        Usados pela `AlunoResource` quando uma linha referencia turma
        que ainda não existe — a turma é criada na hora com esses
        defaults. Sem eles, linhas com turma faltante falham com
        mensagem explicando o que falta.
        """
        return {
            "turno_padrao": request.data.get("turno_padrao"),
            "ano_letivo_padrao": request.data.get("ano_letivo_padrao"),
        }


class ProfessorViewSet(
    ImportExportViewSetMixin,
    EscopoEscolaMixin,
    ReadWritePermissionMixin,
    viewsets.ModelViewSet,
):
    """CRUD de professores. Busca pelo nome do usuário vinculado."""

    queryset = (
        Professor.objects.select_related("usuario", "escola")
        .order_by("usuario__first_name", "usuario__last_name")
    )
    serializer_class = ProfessorSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["ativo"]
    search_fields = [
        "usuario__first_name",
        "usuario__last_name",
        "usuario__username",
    ]
    import_export_resource = ProfessorResource
    import_export_nome_arquivo = "professores"


class LecionamentoViewSet(
    ImportExportViewSetMixin,
    EscopoEscolaMixin,
    ReadWritePermissionMixin,
    viewsets.ModelViewSet,
):
    """CRUD de lecionamentos (vínculo professor × turma × disciplina)."""

    queryset = (
        Lecionamento.objects.select_related(
            "professor__usuario", "turma", "disciplina", "escola"
        ).order_by("turma__ano_letivo", "turma__nome", "disciplina__nome")
    )
    serializer_class = LecionamentoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["professor", "turma", "disciplina", "ativo"]
    import_export_resource = LecionamentoResource
    import_export_nome_arquivo = "lecionamentos"
