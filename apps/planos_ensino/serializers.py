"""Serializers da app planos_ensino."""
from rest_framework import serializers

from apps.common.serializers import (
    AutoEscopoEscolaSerializerMixin,
    validate_escola_do_usuario,
)

from .models import PlanoEnsino


class PlanoEnsinoSerializer(AutoEscopoEscolaSerializerMixin, serializers.ModelSerializer):
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
        # `escola` opcional — `PlanoEnsinoViewSet` usa `AutoEscopoEscolaMixin`.
        extra_kwargs = {"escola": {"required": False}}

    def validate_escola(self, value):
        return validate_escola_do_usuario(
            value,
            self.context.get("request"),
            "Você só pode criar planos na sua própria escola.",
        )

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
