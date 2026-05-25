"""Serializers da app planos_ensino."""
from rest_framework import serializers

from .models import PlanoEnsino


class PlanoEnsinoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanoEnsino
        fields = [
            "id",
            "escola",
            "turma",
            "disciplina",
            "professor",
            "ano_letivo",
            "ementa",
            "conteudo_programatico",
            "objetivos_gerais",
            "objetivos_especificos",
            "habilidades_bncc",
            "carga_horaria",
            "metodologia",
            "recursos",
            "avaliacao",
            "ativo",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]

    def validate_escola(self, value):
        """Recusa payload com `escola` diferente da do usuário autenticado.

        Padrão IDOR já aplicado nas outras apps. Admin/superuser bypassam.
        """
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return value
        user = request.user
        if user.is_superuser or getattr(user, "perfil", None) == "admin":
            return value
        user_escola_id = getattr(user, "escola_id", None)
        if user_escola_id and value.id != user_escola_id:
            raise serializers.ValidationError(
                "Você só pode criar planos na sua própria escola."
            )
        return value

    def validate(self, attrs: dict) -> dict:
        """Espelha invariantes cruzadas do `PlanoEnsino.clean()`.

        PATCH parcial: usa `self.instance` como fallback nos campos
        ausentes.
        """
        escola = attrs.get("escola") or getattr(self.instance, "escola", None)
        turma = attrs.get("turma") or getattr(self.instance, "turma", None)
        disciplina = attrs.get("disciplina") or getattr(
            self.instance, "disciplina", None
        )
        professor = attrs.get("professor")
        if (
            professor is None
            and self.instance is not None
            and "professor" not in attrs
        ):
            professor = self.instance.professor
        ano_letivo = attrs.get("ano_letivo") or getattr(
            self.instance, "ano_letivo", None
        )

        errors: dict[str, str] = {}

        if turma and escola and turma.escola_id != escola.id:
            errors["turma"] = "A turma deve pertencer à mesma escola do plano."

        if disciplina and escola and disciplina.escola_id != escola.id:
            errors["disciplina"] = (
                "A disciplina deve pertencer à mesma escola do plano."
            )

        if professor and escola and professor.escola_id != escola.id:
            errors["professor"] = (
                "O professor deve pertencer à mesma escola do plano."
            )

        if turma and ano_letivo and turma.ano_letivo != ano_letivo:
            errors["ano_letivo"] = (
                "O ano letivo do plano deve coincidir com o da turma."
            )

        if errors:
            raise serializers.ValidationError(errors)
        return attrs
