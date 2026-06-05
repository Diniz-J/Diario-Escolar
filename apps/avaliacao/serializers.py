"""Serializers da app avaliacao."""
from rest_framework import serializers

from apps.common.serializers import (
    AutoEscopoEscolaSerializerMixin,
    validate_escola_do_usuario,
)

from .models import PeriodoAvaliativo


class PeriodoAvaliativoSerializer(
    AutoEscopoEscolaSerializerMixin, serializers.ModelSerializer
):
    """Serializa `PeriodoAvaliativo`.

    - `escola` é opcional no payload: o `AutoEscopoEscolaSerializerMixin`
      injeta a escola do JWT quando ausente. Admin global ainda escolhe
      explicitamente.
    - `estado` é exposto read-only — vem do `model.estado`. Hoje sempre
      'vazio'; nos próximos PRs vai refletir presença de avaliações e
      notas finais.
    - `validate()` chama `instance.clean()` pra disparar a regra de
      não-sobreposição/datas com mensagem clara em vez de IntegrityError.
    """

    estado = serializers.CharField(read_only=True)

    class Meta:
        model = PeriodoAvaliativo
        fields = [
            "id",
            "escola",
            "nome",
            "ordem",
            "ano_letivo",
            "data_inicio",
            "data_fim",
            "ativo",
            "estado",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "estado", "criado_em", "atualizado_em"]
        extra_kwargs = {"escola": {"required": False}}

    def validate_escola(self, value):
        return validate_escola_do_usuario(
            value,
            self.context.get("request"),
            "Você só pode criar períodos avaliativos na sua própria escola.",
        )

    def validate(self, attrs: dict) -> dict:
        """Replica `model.clean()` no nível do serializer.

        Sem isso o `full_clean` só rodaria no admin — pelo DRF, a
        sobreposição quebraria via IntegrityError genérico (ou nem
        quebraria, já que a unique constraint não cobre faixa de datas).
        """
        instance = PeriodoAvaliativo(
            escola=attrs.get("escola")
            or getattr(self.instance, "escola", None),
            nome=attrs.get("nome") or getattr(self.instance, "nome", ""),
            ordem=attrs.get("ordem") or getattr(self.instance, "ordem", 0),
            ano_letivo=attrs.get("ano_letivo")
            or getattr(self.instance, "ano_letivo", 0),
            data_inicio=attrs.get("data_inicio")
            or getattr(self.instance, "data_inicio", None),
            data_fim=attrs.get("data_fim")
            or getattr(self.instance, "data_fim", None),
        )
        # Preserva o pk em update pra que o `exclude(pk=self.pk)` da
        # validação de sobreposição funcione corretamente.
        if self.instance is not None:
            instance.pk = self.instance.pk
        try:
            instance.clean()
        except Exception as exc:
            # `clean()` levanta django.core.exceptions.ValidationError;
            # convertemos pro tipo do DRF pra resposta JSON consistente.
            from django.core.exceptions import ValidationError as DjangoVE

            if isinstance(exc, DjangoVE):
                detalhes = exc.message_dict if hasattr(exc, "message_dict") else {
                    "non_field_errors": exc.messages
                }
                raise serializers.ValidationError(detalhes) from exc
            raise
        return attrs
