"""Serializers da app presenca."""
from datetime import date

from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from apps.common.serializers import (
    AutoEscopoEscolaSerializerMixin,
    validate_escola_do_usuario,
)

from .models import ItemPresenca, RegistroPresenca


class RegistroPresencaSerializer(
    AutoEscopoEscolaSerializerMixin, serializers.ModelSerializer
):
    # Replicar o default do model: o `UniqueTogetherValidator` declarado
    # explicitamente abaixo torna todos os campos required, descartando o
    # default herdado do field. Sem isso, POST sem `data` falha com
    # "Este campo é obrigatório".
    data = serializers.DateField(default=date.today)

    class Meta:
        model = RegistroPresenca
        fields = [
            "id",
            "escola",
            "turma",
            "professor",
            "data",
            "observacao",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]
        # `escola` opcional — `RegistroPresencaViewSet` usa
        # `AutoEscopoEscolaMixin` pra auto-preencher quando o usuário
        # tem escola vinculada.
        extra_kwargs = {"escola": {"required": False}}
        # Mensagem customizada pra UX em pt-BR (sobrescreve o default
        # do DRF baseado na UniqueConstraint do model).
        validators = [
            UniqueTogetherValidator(
                queryset=RegistroPresenca.objects.all(),
                fields=["escola", "turma", "data"],
                message="Já existe chamada para essa turma nesse dia.",
            ),
        ]

    def validate_data(self, value: date) -> date:
        """Bloqueia data futura — replica `RegistroPresenca.clean()`."""
        if value and value > date.today():
            raise serializers.ValidationError(
                "Data do registro não pode estar no futuro."
            )
        return value

    def validate_escola(self, value):
        return validate_escola_do_usuario(
            value,
            self.context.get("request"),
            "Você só pode registrar presença na sua própria escola.",
        )

    def validate(self, attrs: dict) -> dict:
        """Espelha invariantes cruzadas de `RegistroPresenca.clean()`.

        Tratamento de PATCH parcial: usa `self.instance` como fallback
        para os campos ausentes no payload.
        """
        escola = attrs.get("escola") or getattr(self.instance, "escola", None)
        turma = attrs.get("turma") or getattr(self.instance, "turma", None)
        professor = attrs.get("professor")
        if professor is None and self.instance is not None and "professor" not in attrs:
            professor = self.instance.professor

        errors: dict[str, str] = {}

        if turma and escola and turma.escola_id != escola.id:
            errors["turma"] = "A turma deve pertencer à mesma escola do registro."

        if professor and escola and professor.escola_id != escola.id:
            errors["professor"] = (
                "O professor deve pertencer à mesma escola do registro."
            )

        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class ItemPresencaSerializer(serializers.ModelSerializer):
    """Serializer de `ItemPresenca`.

    `escola` é derivado de `registro.escola` no `save()` do model — por
    isso fica fora dos campos editáveis. Aluno e registro são `read_only`
    porque são fixados na criação automática (via `perform_create` do
    registro pai); PATCH é o caso de uso esperado, para mudar `status`
    e `observacao`. Coerência aluno/turma/escola é garantida no momento
    da criação em `RegistroPresencaViewSet.perform_create`.
    """

    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )

    class Meta:
        model = ItemPresenca
        fields = [
            "id",
            "registro",
            "aluno",
            "status",
            "status_display",
            "observacao",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "registro", "aluno", "criado_em", "atualizado_em"]
