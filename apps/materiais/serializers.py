"""Serializers da app materiais (lado do staff)."""
from rest_framework import serializers

from apps.common.serializers import (
    AutoEscopoEscolaSerializerMixin,
    validate_escola_do_usuario,
)

from .models import Material, leciona, validar_link


class MaterialSerializer(AutoEscopoEscolaSerializerMixin, serializers.ModelSerializer):
    """Espelha as invariantes de `Material.clean()` (o DRF não chama o clean)."""

    professor_nome = serializers.CharField(
        source="professor.usuario.get_full_name", read_only=True
    )
    # Declarado à mão: ao montar o `URLField` a partir do modelo, o DRF
    # descarta todo `URLValidator` do model field (field_mapping.py) — o
    # `validar_link` sumia e ficava o padrão do DRF, que aceita ftp/ftps.
    link = serializers.URLField(
        max_length=500, required=False, allow_blank=True, validators=[validar_link]
    )

    class Meta:
        model = Material
        fields = [
            "id",
            "escola",
            "turma",
            "disciplina",
            "professor",
            "professor_nome",
            "titulo",
            "descricao",
            "link",
            "publicado_em",
            "ativo",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "publicado_em", "criado_em", "atualizado_em"]
        # `escola` opcional — auto-preenchida pelo JWT via
        # AutoEscopoEscolaSerializerMixin quando o usuário tem escola.
        extra_kwargs = {"escola": {"required": False}}

    def validate_escola(self, value):
        return validate_escola_do_usuario(
            value,
            self.context.get("request"),
            "Você só pode publicar material na sua própria escola.",
        )

    def validate(self, attrs: dict) -> dict:
        def atual(campo):
            if campo in attrs:
                return attrs[campo]
            return getattr(self.instance, campo, None)

        escola = atual("escola")
        turma = atual("turma")
        disciplina = atual("disciplina")
        professor = atual("professor")

        errors: dict[str, str] = {}
        for nome, valor in (("turma", turma), ("disciplina", disciplina), ("professor", professor)):
            if valor and escola and valor.escola_id != escola.id:
                errors[nome] = f"O campo {nome} deve pertencer à mesma escola do material."

        if professor and turma and disciplina and not leciona(
            professor.id, turma.id, disciplina.id
        ):
            errors["professor"] = (
                "Não há lecionamento ativo deste professor para esta turma "
                "e disciplina."
            )

        if errors:
            raise serializers.ValidationError(errors)
        return attrs
