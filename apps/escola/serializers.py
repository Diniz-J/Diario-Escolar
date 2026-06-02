"""Serializers da app escola."""
from rest_framework import serializers

from apps.common.serializers import (
    AutoEscopoEscolaSerializerMixin,
    validate_escola_do_usuario,
)

from .models import Aluno, Disciplina, Escola, Lecionamento, Professor, Turma


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


# Padrão aplicado nos serializers abaixo (Turma, Disciplina, Aluno,
# Professor, Lecionamento):
# - `escola` no `extra_kwargs` vira `required=False` — o viewset
#   correspondente usa `AutoEscopoEscolaMixin` pra auto-preencher quando
#   o usuário tem escola vinculada (e o frontend omite o campo).
# - `validate_escola` aplica o guard IDOR — admin pode escolher qualquer
#   escola; não-admin só pode escrever na própria mesmo que passe a
#   escola explicitamente no payload (defesa contra um diretor da Escola
#   A mandar `escola=B_id`).
_ESCOLA_OPCIONAL = {"escola": {"required": False}}


class TurmaSerializer(AutoEscopoEscolaSerializerMixin, serializers.ModelSerializer):
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
        extra_kwargs = _ESCOLA_OPCIONAL

    def validate_escola(self, value):
        return validate_escola_do_usuario(
            value,
            self.context.get("request"),
            "Você só pode criar turmas na sua própria escola.",
        )


class DisciplinaSerializer(AutoEscopoEscolaSerializerMixin, serializers.ModelSerializer):
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
        extra_kwargs = _ESCOLA_OPCIONAL

    def validate_escola(self, value):
        return validate_escola_do_usuario(
            value,
            self.context.get("request"),
            "Você só pode criar disciplinas na sua própria escola.",
        )


class AlunoSerializer(AutoEscopoEscolaSerializerMixin, serializers.ModelSerializer):
    # Obrigatórios no cadastro pela API, mesmo sendo blank=True no modelo.
    # O blank existe só para os alunos antigos sem responsável; novos e
    # edições precisam preencher para a notificação de ocorrência funcionar.
    nome_responsavel = serializers.CharField(required=True, allow_blank=False)
    email_responsavel = serializers.EmailField(required=True, allow_blank=False)

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
            "nome_responsavel",
            "email_responsavel",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]
        extra_kwargs = _ESCOLA_OPCIONAL

    def validate_escola(self, value):
        return validate_escola_do_usuario(
            value,
            self.context.get("request"),
            "Você só pode cadastrar alunos na sua própria escola.",
        )

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


class ProfessorSerializer(AutoEscopoEscolaSerializerMixin, serializers.ModelSerializer):
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
            "ativo",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]
        extra_kwargs = _ESCOLA_OPCIONAL

    def validate_escola(self, value):
        return validate_escola_do_usuario(
            value,
            self.context.get("request"),
            "Você só pode cadastrar professores na sua própria escola.",
        )

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
        return attrs


class LecionamentoSerializer(AutoEscopoEscolaSerializerMixin, serializers.ModelSerializer):
    """Serializa o vínculo Professor × Turma × Disciplina.

    `ano_letivo` é exposto read-only via fonte da turma — evita duplicar
    informação no banco e mantém a UI capaz de filtrar por ano sem mais
    um JOIN.
    """

    ano_letivo = serializers.IntegerField(
        source="turma.ano_letivo", read_only=True
    )

    class Meta:
        model = Lecionamento
        fields = [
            "id",
            "escola",
            "professor",
            "turma",
            "disciplina",
            "ano_letivo",
            "ativo",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "ano_letivo", "criado_em", "atualizado_em"]
        extra_kwargs = _ESCOLA_OPCIONAL

    def validate_escola(self, value):
        return validate_escola_do_usuario(
            value,
            self.context.get("request"),
            "Você só pode criar lecionamentos na sua própria escola.",
        )

    def validate(self, attrs: dict) -> dict:
        """Garante alinhamento de escola entre professor, turma e disciplina."""
        instance = self.instance
        professor = attrs.get("professor") or getattr(instance, "professor", None)
        turma = attrs.get("turma") or getattr(instance, "turma", None)
        disciplina = attrs.get("disciplina") or getattr(instance, "disciplina", None)
        escola = attrs.get("escola") or getattr(instance, "escola", None)

        if not escola:
            return attrs

        if professor and professor.escola_id != escola.id:
            raise serializers.ValidationError(
                {"professor": "O professor deve pertencer à mesma escola do lecionamento."}
            )
        if turma and turma.escola_id != escola.id:
            raise serializers.ValidationError(
                {"turma": "A turma deve pertencer à mesma escola do lecionamento."}
            )
        if disciplina and disciplina.escola_id != escola.id:
            raise serializers.ValidationError(
                {"disciplina": "A disciplina deve pertencer à mesma escola do lecionamento."}
            )
        return attrs
