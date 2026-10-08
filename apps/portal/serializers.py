"""Serializers de leitura do portal do responsável.

Só leitura e com campos escolhidos a dedo: o que sai daqui chega a um
usuário externo. Nada de autoria de comunicado, log de entrega de outros
alunos, observação interna de professor ou qualquer dado agregado da turma
(`PORTAL.md`, seção 4.2).
"""
from rest_framework import serializers

from apps.avaliacao.models import PeriodoAvaliativo
from apps.comunicados.models import Comunicado
from apps.escola.models import Aluno
from apps.materiais.models import Material
from apps.ocorrencias.models import Ocorrencia

from .models import Responsavel


class FilhoSerializer(serializers.ModelSerializer):
    turma = serializers.CharField(source="turma.nome", read_only=True)
    ano_letivo = serializers.IntegerField(source="turma.ano_letivo", read_only=True)

    class Meta:
        model = Aluno
        fields = ["id", "nome_completo", "matricula", "turma", "ano_letivo", "ativo"]
        read_only_fields = fields


class PeriodoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PeriodoAvaliativo
        fields = ["id", "nome", "ano_letivo", "data_inicio", "data_fim"]
        read_only_fields = fields


class OcorrenciaPortalSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    # O email da ocorrência já mostra o professor ao responsável; aqui é o
    # mesmo dado, sem id interno.
    professor = serializers.SerializerMethodField()

    class Meta:
        model = Ocorrencia
        fields = [
            "id",
            "data_ocorrencia",
            "descricao",
            "status",
            "status_display",
            "professor",
        ]
        read_only_fields = fields

    def get_professor(self, obj) -> str | None:
        if obj.professor and obj.professor.usuario:
            return obj.professor.usuario.get_full_name() or None
        return None


class MaterialPortalSerializer(serializers.ModelSerializer):
    disciplina = serializers.CharField(source="disciplina.nome", read_only=True)
    professor = serializers.CharField(
        source="professor.usuario.get_full_name", read_only=True
    )

    class Meta:
        model = Material
        fields = ["id", "titulo", "descricao", "link", "disciplina", "professor", "publicado_em"]
        read_only_fields = fields


class ComunicadoPortalSerializer(serializers.ModelSerializer):
    # Quais filhos *deste* responsável o comunicado alcançou. Preenchido
    # pela view (`_alunos_por_comunicado`), sem tocar no log dos outros.
    alunos = serializers.SerializerMethodField()

    class Meta:
        model = Comunicado
        fields = ["id", "titulo", "mensagem", "enviado_em", "alunos"]
        read_only_fields = fields

    def get_alunos(self, obj) -> list[dict]:
        return self.context["alunos_por_comunicado"].get(obj.pk, [])


class ResponsavelAlunoResumoSerializer(serializers.ModelSerializer):
    """Aluno vinculado, como a tela de responsáveis do staff precisa ver."""

    turma = serializers.CharField(source="turma.nome", read_only=True)

    class Meta:
        model = Aluno
        fields = ["id", "nome_completo", "turma", "ativo"]
        read_only_fields = fields


class ResponsavelStaffSerializer(serializers.ModelSerializer):
    """Responsável visto pela secretaria (fatia 6b). Somente leitura.

    Diferente dos outros serializers deste módulo, este NÃO é consumido
    pelo portal: é a tela de gestão do staff. Mesmo assim nada de senha
    sai daqui — `situacao` já diz o que a escola precisa saber sobre o
    acesso, sem expor hash nem token.
    """

    alunos = ResponsavelAlunoResumoSerializer(many=True, read_only=True)
    situacao = serializers.SerializerMethodField()
    situacao_display = serializers.SerializerMethodField()
    # Vem da annotation do viewset (Subquery), não de query por linha.
    convite_expira_em = serializers.DateTimeField(read_only=True, default=None)
    ultimo_acesso = serializers.DateTimeField(
        source="last_login", read_only=True
    )

    class Meta:
        model = Responsavel
        fields = [
            "id",
            "nome",
            "email",
            "ativo",
            "situacao",
            "situacao_display",
            "convite_expira_em",
            "ultimo_acesso",
            "alunos",
            "criado_em",
        ]
        read_only_fields = fields

    # `PORTAL.md` lista três situações (sem convite / convidado / ativo).
    # Duas foram acrescentadas porque mostrar o contrário seria mentira:
    # `convite_expirado` (o convite tem 7 dias e o pai não usou — exibir
    # "convidado" faria a secretaria esperar por nada) e `inativo` (a conta
    # foi desativada, então convidar não é o próximo passo).
    SITUACOES = {
        "inativo": "Inativo",
        "ativo": "Acesso ativo",
        "convidado": "Convite enviado",
        "convite_expirado": "Convite expirado",
        "sem_convite": "Sem convite",
    }

    def get_situacao(self, obj) -> str:
        if not obj.ativo:
            return "inativo"
        # `has_usable_password` lê o campo já carregado: sem query extra.
        if obj.has_usable_password():
            return "ativo"
        if getattr(obj, "tem_convite_pendente", False):
            return "convidado"
        if getattr(obj, "tem_convite", False):
            return "convite_expirado"
        return "sem_convite"

    def get_situacao_display(self, obj) -> str:
        return self.SITUACOES[self.get_situacao(obj)]
