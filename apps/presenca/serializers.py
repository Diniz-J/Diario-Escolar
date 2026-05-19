"""Serializers da app presenca."""
from datetime import date

from rest_framework import serializers

from .models import ItemPresenca, RegistroPresenca


class RegistroPresencaSerializer(serializers.ModelSerializer):
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

    def validate_data(self, value: date) -> date:
        """Bloqueia data futura — replica `RegistroPresenca.clean()`."""
        if value and value > date.today():
            raise serializers.ValidationError(
                "Data do registro não pode estar no futuro."
            )
        return value

    def validate_escola(self, value):
        """Recusa payload com `escola` diferente da do usuário autenticado.

        Mesmo guard de IDOR aplicado em `OcorrenciaSerializer`: não-admin
        só registra na própria escola; admin/superuser bypassam.
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
                "Você só pode registrar presença na sua própria escola."
            )
        return value

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
    isso fica fora dos campos editáveis. Aluno e registro normalmente são
    fixados na criação automática (via `perform_create` do registro pai);
    PATCH é o caso de uso esperado, para mudar `status` e `observacao`.
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

    def validate(self, attrs: dict) -> dict:
        """Em PATCH, garante que aluno/registro continuem coerentes.

        Os campos `aluno` e `registro` são read_only — então em prática
        este `validate` blinda contra mudanças futuras nessa lista. Hoje
        ele é defensivo: se o registro pai for atualizado e `aluno.turma`
        mudar, o item pode ficar inconsistente; o `clean()` do model
        captura isso ao reapurar.
        """
        instance = self.instance
        if instance is None:
            return attrs

        aluno = instance.aluno
        registro = instance.registro
        if aluno.turma_id != registro.turma_id:
            raise serializers.ValidationError(
                {"aluno": "O aluno deve pertencer à turma do registro de presença."}
            )
        if aluno.escola_id != registro.escola_id:
            raise serializers.ValidationError(
                {"aluno": "O aluno deve pertencer à mesma escola do registro."}
            )
        return attrs
