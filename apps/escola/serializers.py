"""Serializers da app escola."""
from rest_framework import serializers

from .models import Aluno, Disciplina, Escola, Professor, Turma


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


class ProfessorSerializer(serializers.ModelSerializer):
    nome_completo = serializers.CharField(
        source="usuario.get_full_name", read_only=True
    )

    class Meta:
        model = Professor
        fields = [
            "id",
            "escola",
            "usuario",
            "nome_completo",
            "disciplinas",
            "ativo",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]

    def validate(self, attrs: dict) -> dict:
        """Replica a invariante de `Professor.clean()` (mesma escola que o usuário).

        Aplica também aos updates: usa o instance como fallback quando o
        campo não vem no payload (PATCH parcial).
        """
        usuario = attrs.get("usuario") or getattr(self.instance, "usuario", None)
        escola = attrs.get("escola") or getattr(self.instance, "escola", None)
        if usuario and escola and usuario.escola_id and usuario.escola_id != escola.id:
            raise serializers.ValidationError(
                {"usuario": "O usuário deve pertencer à mesma escola do professor."}
            )

        disciplinas = attrs.get("disciplinas")
        if disciplinas and escola:
            ids_outras_escolas = [
                d.id for d in disciplinas if d.escola_id != escola.id
            ]
            if ids_outras_escolas:
                raise serializers.ValidationError(
                    {"disciplinas": "Todas as disciplinas devem pertencer à mesma escola."}
                )
        return attrs
