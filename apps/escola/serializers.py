"""Serializers da app escola."""
from rest_framework import serializers

from .models import Aluno, Disciplina, Escola, Turma


class EscolaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Escola
        fields = [
            "id",
            "nome",
            "cnpj",
            "ativa",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]


class TurmaSerializer(serializers.ModelSerializer):
    turno_display = serializers.CharField(
        source="get_turno_display", read_only=True
    )

    class Meta:
        model = Turma
        fields = [
            "id",
            "escola",
            "nome",
            "turno",
            "turno_display",
            "ano_letivo",
            "ativa",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]


class DisciplinaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disciplina
        fields = [
            "id",
            "escola",
            "nome",
            "ativa",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]


class AlunoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Aluno
        fields = [
            "id",
            "escola",
            "matricula",
            "nome_completo",
            "data_nascimento",
            "turma",
            "ativo",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]

    def validate(self, attrs: dict) -> dict:
        """Garante que turma e aluno pertencem à mesma escola.

        Replica a invariante de `Aluno.clean()` no nível do serializer para
        retornar 400 com mensagem clara em vez de IntegrityError ou erro
        genérico do `full_clean`.
        """
        turma = attrs.get("turma") or getattr(self.instance, "turma", None)
        escola = attrs.get("escola") or getattr(self.instance, "escola", None)
        if turma and escola and turma.escola_id != escola.id:
            raise serializers.ValidationError(
                {"turma": "A turma deve pertencer à mesma escola do aluno."}
            )
        return attrs
