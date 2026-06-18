"""Views da app aulas — diário de classe do professor + visto da direção.

Padrão de permissão:
- Leitura/escrita: admin/diretor/secretaria/coordenador/professor/inspetor.
- Conferência (`conferir`): só admin/diretor/secretaria/coordenador.

Escopo de visibilidade:
- Direção (admin/diretor/secretaria/coordenador) vê os registros de toda a escola.
- Professor/inspetor vê e edita apenas os próprios registros.

A transição pra `conferido` é exclusiva da action `conferir` — o serializer
recusa `status=conferido`, então não há como o professor se autoconferir.
"""
import unicodedata
from datetime import date

from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.common.permissions import (
    IsAdminOrDiretor,
    IsAdminOrDiretorOrProfessor,
)
from apps.common.views import EscopoEscolaMixin, ReadWritePermissionMixin
from apps.escola.models import Disciplina, Professor, Turma

from .filters import RegistroAulaFilter
from .models import RegistroAula
from .serializers import RegistroAulaSerializer
from .services import projetar_agenda

# Perfis que enxergam o diário da escola inteira (não só o próprio).
_PERFIS_DIRECAO = frozenset({"diretor", "secretaria", "coordenador"})

_MESES = [
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]


def _render_pdf(html_str: str) -> bytes:
    """Helper module-level: renderiza HTML→PDF via WeasyPrint.

    Mesmo padrão do boletim (apps/boletins/views.py): nível de função pra
    ser mockável nos testes e com import lazy do WeasyPrint (que só carrega
    libs do sistema quando de fato chamado — `manage.py check` no Windows
    continua funcionando).
    """
    from weasyprint import HTML  # noqa: WPS433

    return HTML(string=html_str).write_pdf()


def _agrupar_por_mes(registros):
    """Agrupa os registros (já ordenados por -data) em seções por mês."""
    grupos: list[dict] = []
    atual = None
    for r in registros:
        chave = (r.data.year, r.data.month)
        if atual is None or atual["chave"] != chave:
            atual = {
                "chave": chave,
                "label": f"{_MESES[r.data.month - 1]} {r.data.year}",
                "aulas": [],
            }
            grupos.append(atual)
        atual["aulas"].append(r)
    return grupos


def _eh_direcao(user) -> bool:
    """True para admin/superuser e perfis de direção (diretor/secretaria)."""
    if getattr(user, "is_superuser", False):
        return True
    perfil = getattr(user, "perfil", None)
    return perfil == "admin" or perfil in _PERFIS_DIRECAO


def _professor_do_usuario(user):
    """Retorna o `Professor` vinculado ao usuário, ou None se não houver."""
    try:
        return user.professor
    except (AttributeError, ObjectDoesNotExist):
        return None


class _AulaReadWriteMixin(ReadWritePermissionMixin):
    """Leitura e escrita liberadas pra direção + professor/inspetor."""

    READ_PERMISSION = IsAdminOrDiretorOrProfessor
    WRITE_PERMISSION = IsAdminOrDiretorOrProfessor


class RegistroAulaViewSet(
    EscopoEscolaMixin, _AulaReadWriteMixin, viewsets.ModelViewSet
):
    """CRUD do diário de aula + conferência da direção + agenda projetada."""

    queryset = (
        RegistroAula.objects.select_related(
            "turma",
            "disciplina",
            "professor",
            "professor__usuario",
            "conferido_por",
            "escola",
        ).order_by("-data")
    )
    serializer_class = RegistroAulaSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = RegistroAulaFilter

    def get_queryset(self):
        """Direção vê toda a escola; professor/inspetor só os próprios."""
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return qs.none()
        if _eh_direcao(user):
            return qs
        professor = _professor_do_usuario(user)
        if professor is None:
            return qs.none()
        return qs.filter(professor_id=professor.id)

    def get_permissions(self):
        if self.action == "conferir":
            return [IsAdminOrDiretor()]
        return super().get_permissions()

    def perform_create(self, serializer) -> None:
        """Professor só cria registro pra si mesmo; direção pode escolher.

        Bloqueia (em vez de sobrescrever) quando o docente tenta lançar em
        nome de outro: a validação de lecionamento já rodou pro `professor`
        do payload, então sobrescrever desalinharia a invariante.
        """
        user = self.request.user
        if not _eh_direcao(user):
            proprio = _professor_do_usuario(user)
            if proprio is None or serializer.validated_data.get("professor") != proprio:
                raise PermissionDenied(
                    "Você só pode lançar aulas em seu próprio nome."
                )
        serializer.save()

    @action(detail=True, methods=["post"])
    def conferir(self, request, pk=None):
        """Direção dá o visto: `lancado` → `conferido` (grava quem/quando)."""
        registro = self.get_object()
        if registro.status != RegistroAula.Status.LANCADO:
            return Response(
                {
                    "detail": "Só é possível conferir uma aula com status "
                    "'lançado'."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        registro.status = RegistroAula.Status.CONFERIDO
        registro.conferido_por = request.user
        registro.conferido_em = timezone.now()
        registro.save(
            update_fields=[
                "status",
                "conferido_por",
                "conferido_em",
                "atualizado_em",
            ]
        )
        return Response(self.get_serializer(registro).data)

    @action(detail=False, methods=["get"])
    def agenda(self, request):
        """Projeta os slots de aula de um lecionamento num mês.

        Query params: `turma`, `disciplina`, `mes` (YYYY-MM) obrigatórios;
        `professor` opcional (default: o professor logado).
        """
        turma_id = request.query_params.get("turma")
        disciplina_id = request.query_params.get("disciplina")
        mes_param = request.query_params.get("mes")
        professor_param = request.query_params.get("professor")

        if not (turma_id and disciplina_id and mes_param):
            return Response(
                {
                    "detail": "Parâmetros obrigatórios: turma, disciplina, "
                    "mes (YYYY-MM)."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            ano_str, mes_str = mes_param.split("-")
            ano, mes = int(ano_str), int(mes_str)
            date(ano, mes, 1)
        except (ValueError, TypeError):
            return Response(
                {"detail": "mes inválido — use o formato YYYY-MM."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if professor_param:
            professor_id = professor_param
        else:
            professor = _professor_do_usuario(request.user)
            if professor is None:
                return Response(
                    {"detail": "Informe o parâmetro professor."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            professor_id = professor.id

        turma = Turma.objects.filter(id=turma_id).first()
        if turma is None:
            return Response(
                {"detail": "Turma não encontrada."},
                status=status.HTTP_404_NOT_FOUND,
            )
        # Guard de escopo: não-direção só projeta agenda da própria escola.
        if not _eh_direcao(request.user) and turma.escola_id != getattr(
            request.user, "escola_id", None
        ):
            return Response(
                {"detail": "Turma fora do seu escopo."},
                status=status.HTTP_404_NOT_FOUND,
            )

        slots = projetar_agenda(
            escola_id=turma.escola_id,
            professor_id=professor_id,
            turma_id=turma_id,
            disciplina_id=disciplina_id,
            ano=ano,
            mes=mes,
        )
        return Response(slots)

    @action(detail=False, methods=["get"])
    def pdf(self, request):
        """Exporta o diário (recortado pelos filtros) em PDF com assinatura.

        Reaproveita `get_queryset` (escopo por perfil) + `RegistroAulaFilter`,
        então o PDF sai com o mesmo recorte da tela (professor/turma/
        disciplina/status/período). O template é agnóstico do renderizador.
        """
        registros = list(self.filter_queryset(self.get_queryset()))

        # Cabeçalho: resolve o professor do filtro (a ficha sempre manda),
        # respeitando o escopo de escola pra não vazar nome de outra escola.
        professor = None
        professor_id = request.query_params.get("professor")
        if professor_id:
            professor = (
                self._professores_no_escopo()
                .filter(pk=professor_id)
                .select_related("usuario")
                .first()
            )

        # Lista vazia: o cabeçalho ainda precisa da escola — recai no user.
        if registros:
            escola_nome = registros[0].escola.nome
        else:
            escola_usuario = getattr(request.user, "escola", None)
            escola_nome = escola_usuario.nome if escola_usuario else ""

        contexto = {
            "professor_nome": (
                professor.usuario.get_full_name() if professor else None
            ),
            "escola_nome": escola_nome,
            "filtros": self._descrever_filtros(request),
            "grupos": _agrupar_por_mes(registros),
            "total": len(registros),
            "gerado_em": timezone.localtime(),
        }
        # WeasyPrint não tem servidor HTTP: a logo precisa de caminho
        # absoluto (file://). Mesmo padrão do boletim.
        from django.contrib.staticfiles import finders

        contexto["logo_path"] = (
            finders.find("branding/diario-diniz-badge-128.png") or ""
        )

        html_str = render_to_string("aula_diario_pdf.html", contexto)
        pdf_bytes = _render_pdf(html_str)

        if professor:
            nome = (
                professor.usuario.get_full_name()
                or professor.usuario.username
            )
            # ASCII-safe: tira acentos pra Content-Disposition não engasgar
            # em browsers antigos / proxies.
            nome_ascii = (
                unicodedata.normalize("NFKD", nome)
                .encode("ascii", "ignore")
                .decode("ascii")
            )
            slug = nome_ascii.strip().lower().replace(" ", "_")
            nome_arquivo = f"diario_{slug}.pdf" if slug else "diario_aula.pdf"
        else:
            nome_arquivo = "diario_aula.pdf"

        resposta = HttpResponse(pdf_bytes, content_type="application/pdf")
        resposta["Content-Disposition"] = (
            f'attachment; filename="{nome_arquivo}"'
        )
        return resposta

    def _professores_no_escopo(self):
        """Professores visíveis pra request (mesmo escopo de escola da view)."""
        qs = Professor.objects.all()
        user = self.request.user
        if _eh_direcao(user):
            escola_id = getattr(user, "escola_id", None)
            return qs.filter(escola_id=escola_id) if escola_id else qs
        proprio = _professor_do_usuario(user)
        return qs.filter(pk=proprio.id) if proprio else qs.none()

    def _descrever_filtros(self, request) -> str:
        """Monta um rótulo legível dos filtros aplicados, pro cabeçalho."""
        partes = []

        # Datas em DD/MM/YYYY com wording natural pra range parcial.
        inicio = self._formatar_data_iso(request.query_params.get("data_inicio"))
        fim = self._formatar_data_iso(request.query_params.get("data_fim"))
        if inicio and fim:
            partes.append(f"{inicio} a {fim}")
        elif inicio:
            partes.append(f"a partir de {inicio}")
        elif fim:
            partes.append(f"até {fim}")

        # Turma e disciplina resolvidas por nome no escopo do usuário.
        turma_id = request.query_params.get("turma")
        if turma_id:
            nome_turma = self._nome_no_escopo(Turma, turma_id)
            if nome_turma:
                partes.append(f"Turma: {nome_turma}")

        disciplina_id = request.query_params.get("disciplina")
        if disciplina_id:
            nome_disc = self._nome_no_escopo(Disciplina, disciplina_id)
            if nome_disc:
                partes.append(f"Disciplina: {nome_disc}")

        status_filtro = request.query_params.get("status")
        if status_filtro:
            rotulo = dict(RegistroAula.Status.choices).get(
                status_filtro, status_filtro
            )
            partes.append(f"Status: {rotulo}")

        return " · ".join(partes) if partes else "Todas as aulas"

    @staticmethod
    def _formatar_data_iso(valor):
        """Converte 'YYYY-MM-DD' em 'DD/MM/YYYY' (devolve cru se inválido)."""
        if not valor:
            return None
        try:
            return date.fromisoformat(valor).strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            return valor

    def _nome_no_escopo(self, modelo, pk):
        """Resolve o nome de Turma/Disciplina respeitando a escola do user.

        Admin/superuser passa qualquer escola; outros só leem nomes da
        própria escola — evita vazar nome de outro tenant via id chutado.
        """
        qs = modelo.objects.filter(pk=pk)
        user = self.request.user
        if not getattr(user, "is_superuser", False) and getattr(
            user, "perfil", None
        ) != "admin":
            escola_id = getattr(user, "escola_id", None)
            if escola_id:
                qs = qs.filter(escola_id=escola_id)
            else:
                return None
        obj = qs.first()
        return obj.nome if obj else None
