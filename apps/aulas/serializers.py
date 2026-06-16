"""Serializers da app aulas."""
from datetime import date

from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from apps.common.serializers import (
    AutoEscopoEscolaSerializerMixin,
    validate_escola_do_usuario,
)
from apps.escola.models import Lecionamento

from .models import RegistroAula


class RegistroAulaSerializer(
    AutoEscopoEscolaSerializerMixin, serializers.ModelSerializer
):
    """Serializer de `RegistroAula`.

    `status` aceita só `rascunho`/`lancado` aqui — a transição pra
    `conferido` é exclusiva da action `conferir` da view (direção).
    `conferido_por`/`conferido_em` são read-only pelo mesmo motivo.
    """

    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    conferido_por_nome = serializers.CharField(
        source="conferido_por.get_full_name", read_only=True, default=None
    )

    class Meta:
        model = RegistroAula
        fields = [
            "id",
            "escola",
            "turma",
            "disciplina",
            "professor",
            "data",
            "conteudo",
            "status",
            "status_display",
            "conferido_por",
            "conferido_por_nome",
            "conferido_em",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = [
            "id",
            "conferido_por",
            "conferido_em",
            "criado_em",
            "atualizado_em",
        ]
        # `escola` opcional — auto-preenchida pelo JWT via
        # AutoEscopoEscolaSerializerMixin quando o usuário tem escola.
        extra_kwargs = {"escola": {"required": False}}
        validators = [
            UniqueTogetherValidator(
                queryset=RegistroAula.objects.all(),
                fields=["escola", "turma", "disciplina", "data"],
                message="Já existe registro de aula para essa turma, "
                "disciplina e dia.",
            ),
        ]

    def validate_data(self, value: date) -> date:
        """Bloqueia data futura — replica `RegistroAula.clean()`."""
        if value and value > date.today():
            raise serializers.ValidationError(
                "A data da aula não pode estar no futuro."
            )
        return value

    def validate_status(self, value: str) -> str:
        """A conferência é feita pela direção via action própria."""
        if value == RegistroAula.Status.CONFERIDO:
            raise serializers.ValidationError(
                "A conferência é feita pela direção, não por este campo."
            )
        return value

    def validate_escola(self, value):
        return validate_escola_do_usuario(
            value,
            self.context.get("request"),
            "Você só pode registrar aula na sua própria escola.",
        )

    def validate(self, attrs: dict) -> dict:
        """Espelha invariantes cruzadas de `RegistroAula.clean()`."""

        def atual(campo, default=None):
            if campo in attrs:
                return attrs[campo]
            return getattr(self.instance, campo, default)

        escola = atual("escola")
        turma = atual("turma")
        disciplina = atual("disciplina")
        professor = atual("professor")
        status = atual("status", RegistroAula.Status.RASCUNHO)
        conteudo = atual("conteudo", "") or ""

        errors: dict[str, str] = {}

        # Aula já conferida não pode ser reaberta/editada pelo professor.
        if self.instance and self.instance.status == RegistroAula.Status.CONFERIDO:
            raise serializers.ValidationError(
                "Esta aula já foi conferida pela direção e não pode mais "
                "ser editada."
            )

        if turma and escola and turma.escola_id != escola.id:
            errors["turma"] = "A turma deve pertencer à mesma escola do registro."

        if disciplina and escola and disciplina.escola_id != escola.id:
            errors["disciplina"] = (
                "A disciplina deve pertencer à mesma escola do registro."
            )

        if professor and escola and professor.escola_id != escola.id:
            errors["professor"] = (
                "O professor deve pertencer à mesma escola do registro."
            )

        if professor and turma and disciplina:
            existe_vinculo = Lecionamento.objects.filter(
                professor=professor,
                turma=turma,
                disciplina=disciplina,
                ativo=True,
            ).exists()
            if not existe_vinculo:
                errors["professor"] = (
                    "Não há lecionamento ativo deste professor para esta "
                    "turma e disciplina."
                )

        if status != RegistroAula.Status.RASCUNHO and not conteudo.strip():
            errors["conteudo"] = "Informe o conteúdo da aula antes de lançar."

        if errors:
            raise serializers.ValidationError(errors)
        return attrs
