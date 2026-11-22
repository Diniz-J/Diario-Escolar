"""Serializers da app grade.

Espelham as invariantes de `clean()` à mão, como `materiais` e `aulas` — o
DRF não chama o `clean()` do modelo. (O financeiro roda o `clean()` sobre
uma cópia porque tem cinco invariantes por modelo; aqui são três, e
duplicá-las custa menos que a indireção.)

`AulaGradeSerializer` expõe disciplina, professor e horário derivados
porque a tela de montagem da grade renderiza a semana inteira — sem eles,
seria uma requisição por slot só pra descobrir o nome da matéria.
"""
from rest_framework import serializers

from apps.common.serializers import (
    AutoEscopoEscolaSerializerMixin,
    validate_escola_do_usuario,
)

from apps.common.permissions import eh_admin_global
from apps.escola.models import Turma

from .models import AulaGrade, TempoAula

_ESCOLA_OPCIONAL = {"escola": {"required": False}}


class TempoAulaSerializer(
    AutoEscopoEscolaSerializerMixin, serializers.ModelSerializer
):
    """Catálogo de horários da escola, por turno."""

    turno_display = serializers.CharField(
        source="get_turno_display", read_only=True
    )

    class Meta:
        model = TempoAula
        fields = [
            "id",
            "escola",
            "turno",
            "turno_display",
            "ordem",
            "hora_inicio",
            "hora_fim",
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
            "Você só pode cadastrar tempos de aula na sua própria escola.",
        )

    def validate_ordem(self, value: int) -> int:
        if value is not None and value < 1:
            raise serializers.ValidationError("A ordem do tempo começa em 1.")
        return value

    def validate(self, attrs: dict) -> dict:
        """Duração positiva — espelha `TempoAula.clean()`."""
        inicio = attrs.get("hora_inicio") or getattr(
            self.instance, "hora_inicio", None
        )
        fim = attrs.get("hora_fim") or getattr(self.instance, "hora_fim", None)

        if inicio and fim and fim <= inicio:
            raise serializers.ValidationError(
                {"hora_fim": "O fim do tempo deve ser depois do início."}
            )
        return attrs


class AulaGradeSerializer(
    AutoEscopoEscolaSerializerMixin, serializers.ModelSerializer
):
    """Slot da grade. `turma` é derivada do lecionamento, nunca do payload."""

    dia_semana_display = serializers.CharField(
        source="get_dia_semana_display", read_only=True
    )
    turma_nome = serializers.CharField(source="turma.nome", read_only=True)
    disciplina = serializers.IntegerField(
        source="lecionamento.disciplina_id", read_only=True
    )
    disciplina_nome = serializers.CharField(
        source="lecionamento.disciplina.nome", read_only=True
    )
    professor = serializers.IntegerField(
        source="lecionamento.professor_id", read_only=True
    )
    professor_nome = serializers.CharField(
        source="lecionamento.professor.usuario.get_full_name", read_only=True
    )
    tempo_ordem = serializers.IntegerField(source="tempo.ordem", read_only=True)
    tempo_hora_inicio = serializers.TimeField(
        source="tempo.hora_inicio", read_only=True
    )
    tempo_hora_fim = serializers.TimeField(
        source="tempo.hora_fim", read_only=True
    )

    class Meta:
        model = AulaGrade
        fields = [
            "id",
            "escola",
            "lecionamento",
            "turma",
            "turma_nome",
            "dia_semana",
            "dia_semana_display",
            "tempo",
            "tempo_ordem",
            "tempo_hora_inicio",
            "tempo_hora_fim",
            "disciplina",
            "disciplina_nome",
            "professor",
            "professor_nome",
            "ativo",
            "criado_em",
            "atualizado_em",
        ]
        # `turma` é read-only de propósito: é cópia do lecionamento (ver
        # docstring de `models.py`), e aceitá-la do payload permitiria um
        # slot cuja turma não é a do vínculo.
        read_only_fields = ["id", "turma", "criado_em", "atualizado_em"]
        extra_kwargs = _ESCOLA_OPCIONAL

    def validate_escola(self, value):
        return validate_escola_do_usuario(
            value,
            self.context.get("request"),
            "Você só pode montar a grade da sua própria escola.",
        )

    def validate(self, attrs: dict) -> dict:
        """Espelha `AulaGrade.clean()` e deriva `turma` do lecionamento.

        A duplicata precisa de checagem explícita: o unique do modelo é
        **parcial** (`condition=ativo=True`) e o DRF não monta validator
        automático pra constraint condicional — sem isto, o segundo slot no
        mesmo horário estouraria `IntegrityError` como 500 em vez de 400.
        É a mesma pegadinha registrada no `FINANCEIRO.md` §5 pra
        competência repetida.
        """
        instance = self.instance
        escola = attrs.get("escola") or getattr(instance, "escola", None)
        lecionamento = attrs.get("lecionamento") or getattr(
            instance, "lecionamento", None
        )
        tempo = attrs.get("tempo") or getattr(instance, "tempo", None)
        dia_semana = attrs.get("dia_semana")
        if dia_semana is None:
            dia_semana = getattr(instance, "dia_semana", None)
        ativo = attrs.get("ativo")
        if ativo is None:
            ativo = getattr(instance, "ativo", True)

        errors: dict[str, str] = {}

        if escola:
            if lecionamento and lecionamento.escola_id != escola.id:
                errors["lecionamento"] = (
                    "O lecionamento deve pertencer à mesma escola da grade."
                )
            if tempo and tempo.escola_id != escola.id:
                errors["tempo"] = (
                    "O tempo deve pertencer à mesma escola da grade."
                )

        turma = getattr(lecionamento, "turma", None)

        if turma and tempo and tempo.turno != turma.turno:
            errors["tempo"] = "O tempo deve ser do mesmo turno da turma."

        if errors:
            raise serializers.ValidationError(errors)

        if turma is not None:
            attrs["turma"] = turma

        if ativo and turma and tempo and dia_semana is not None:
            conflito = AulaGrade.objects.filter(
                escola=escola,
                turma=turma,
                dia_semana=dia_semana,
                tempo=tempo,
                ativo=True,
            )
            if instance is not None:
                conflito = conflito.exclude(pk=instance.pk)
            if conflito.exists():
                raise serializers.ValidationError(
                    {
                        "tempo": (
                            "Esta turma já tem aula neste dia e neste tempo."
                        )
                    }
                )

        return attrs


class ClonarGradeSerializer(serializers.Serializer):
    """Entrada da action `clonar`: de qual turma pra qual turma.

    As duas turmas são validadas contra a escola de quem está logado, e
    não só entre si: um par consistente de outra escola passaria pelo
    service (que compara origem com destino) sem nada a reclamar. É a
    mesma dupla camada do vínculo do portal (`RESPONSAVEIS.md`).
    """

    turma_origem = serializers.PrimaryKeyRelatedField(
        queryset=Turma.objects.all()
    )
    turma_destino = serializers.PrimaryKeyRelatedField(
        queryset=Turma.objects.all()
    )

    def validate(self, attrs: dict) -> dict:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user is None or eh_admin_global(user):
            return attrs

        escola_id = getattr(user, "escola_id", None)
        for campo in ("turma_origem", "turma_destino"):
            turma = attrs[campo]
            if not escola_id or turma.escola_id != escola_id:
                raise serializers.ValidationError(
                    {campo: "Você só pode clonar grade da sua própria escola."}
                )
        return attrs
