"""Serializers da app ocorrencias."""
from datetime import date

from rest_framework import serializers

from apps.common.serializers import (
    AutoEscopoEscolaSerializerMixin,
    validate_escola_do_usuario,
)

from .models import Ocorrencia


class OcorrenciaSerializer(AutoEscopoEscolaSerializerMixin, serializers.ModelSerializer):
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )

    class Meta:
        model = Ocorrencia
        fields = [
            "id",
            "escola",
            "turma",
            "aluno",
            "professor",
            "descricao",
            "data_ocorrencia",
            "status",
            "status_display",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]
        # `escola` opcional — `OcorrenciaViewSet` usa `AutoEscopoEscolaMixin`
        # pra auto-preencher quando o usuário tem escola vinculada.
        extra_kwargs = {"escola": {"required": False}}

    def validate_data_ocorrencia(self, value: date) -> date:
        """Bloqueia data futura — replica a invariante do model.clean()."""
        if value and value > date.today():
            raise serializers.ValidationError(
                "Data da ocorrência não pode estar no futuro."
            )
        return value

    def validate_escola(self, value):
        return validate_escola_do_usuario(
            value,
            self.context.get("request"),
            "Você só pode registrar ocorrências na sua própria escola.",
        )

    def validate(self, attrs: dict) -> dict:
        """Espelha as invariantes cruzadas de `Ocorrencia.clean()`.

        Garante 400 com mensagens por campo em vez de IntegrityError ou erro
        genérico do `full_clean`. Usa `self.instance` como fallback nos
        campos ausentes em PATCH parcial.
        """
        escola = attrs.get("escola") or getattr(self.instance, "escola", None)
        turma = attrs.get("turma") or getattr(self.instance, "turma", None)
        aluno = attrs.get("aluno") or getattr(self.instance, "aluno", None)
        professor = attrs.get("professor")
        if professor is None and self.instance is not None and "professor" not in attrs:
            professor = self.instance.professor

        errors: dict[str, str] = {}

        if aluno and escola and aluno.escola_id != escola.id:
            errors["aluno"] = "O aluno deve pertencer à mesma escola da ocorrência."

        if turma and aluno and aluno.turma_id != turma.id:
            errors["turma"] = "A turma da ocorrência deve ser a turma atual do aluno."

        if professor and escola and professor.escola_id != escola.id:
            errors["professor"] = (
                "O professor deve pertencer à mesma escola da ocorrência."
            )

        if errors:
            raise serializers.ValidationError(errors)
        return attrs
