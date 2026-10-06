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
from apps.ocorrencias.models import Ocorrencia


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
