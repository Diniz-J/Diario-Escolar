"""Serializers da app presenca."""
from datetime import date

from rest_framework import serializers

from apps.common.serializers import (
    AutoEscopoEscolaSerializerMixin,
    validate_escola_do_usuario,
)
from apps.grade.models import TempoAula

from .models import (
    ItemPresenca,
    RegistroPresenca,
    erro_de_tempos,
    tempos_padrao,
    tempos_sobrepostos,
)


class RegistroPresencaSerializer(
    AutoEscopoEscolaSerializerMixin, serializers.ModelSerializer
):
    """Chamada de um bloco de tempos (ver `PRESENCA.md`).

    `tempos` é **opcional no payload** e, omitido, cobre o dia todo (o
    turno inteiro da turma, ou um tempo onde não há catálogo). Isso é o
    que mantém o cliente que ainda não manda o campo — a tela de chamada
    atual — funcionando com a mesma semântica que a chamada diária tinha:
    uma chamada por dia, valendo o dia.
    """

    data = serializers.DateField(default=date.today)
    # `required=False` com a dedução no `validate`: o campo é obrigatório
    # no modelo (não-vazio), mas quem não o manda recebe o dia todo.
    tempos = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=False,
    )
    # Exposto pra a tela mostrar o horário do bloco sem resolver o
    # catálogo por conta própria.
    tempos_detalhe = serializers.SerializerMethodField()
    disciplina_nome = serializers.CharField(
        source="disciplina.nome", read_only=True, default=None
    )

    class Meta:
        model = RegistroPresenca
        fields = [
            "id",
            "escola",
            "turma",
            "professor",
            "disciplina",
            "disciplina_nome",
            "data",
            "tempos",
            "tempos_detalhe",
            "observacao",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]
        # `escola` opcional — `RegistroPresencaViewSet` usa
        # `AutoEscopoEscolaMixin` pra auto-preencher quando o usuário
        # tem escola vinculada.
        extra_kwargs = {"escola": {"required": False}}

    def get_tempos_detalhe(self, obj) -> list[dict]:
        """Horário de cada tempo do bloco, na ordem.

        Resolvido pelo ordinal contra o catálogo **atual**: o registro
        guarda o ordinal de propósito (`PRESENCA.md` §2.9), então uma
        chamada antiga reimpressa depois de a escola mexer nos horários
        mostra o horário novo ao lado do tempo correto. Tempo que saiu do
        catálogo aparece só com o ordinal.
        """
        if not obj.tempos:
            return []
        horarios = {}
        if obj.turma_id:
            horarios = {
                tempo.ordem: tempo
                for tempo in TempoAula.objects.filter(
                    escola_id=obj.turma.escola_id,
                    turno=obj.turma.turno,
                    ordem__in=obj.tempos,
                )
            }
        detalhe = []
        for ordem in obj.tempos:
            tempo = horarios.get(ordem)
            detalhe.append(
                {
                    "ordem": ordem,
                    "hora_inicio": (
                        tempo.hora_inicio.isoformat() if tempo else None
                    ),
                    "hora_fim": tempo.hora_fim.isoformat() if tempo else None,
                }
            )
        return detalhe

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
        disciplina = attrs.get("disciplina")
        if (
            disciplina is None
            and self.instance is not None
            and "disciplina" not in attrs
        ):
            disciplina = self.instance.disciplina

        errors: dict[str, str] = {}

        if turma and escola and turma.escola_id != escola.id:
            errors["turma"] = "A turma deve pertencer à mesma escola do registro."

        if professor and escola and professor.escola_id != escola.id:
            errors["professor"] = (
                "O professor deve pertencer à mesma escola do registro."
            )

        if disciplina and escola and disciplina.escola_id != escola.id:
            errors["disciplina"] = (
                "A disciplina deve pertencer à mesma escola do registro."
            )

        # Bloco de tempos: omitido significa o dia todo (ver docstring da
        # classe). A dedução acontece aqui e não num `default=` porque
        # depende da turma, que só se conhece com o payload em mãos.
        tempos = attrs.get("tempos")
        if tempos is None:
            tempos = (
                list(self.instance.tempos)
                if self.instance is not None
                else (tempos_padrao(turma) if turma else [])
            )
            attrs["tempos"] = tempos

        erro_tempos = erro_de_tempos(tempos, turma)
        if erro_tempos:
            errors["tempos"] = erro_tempos
        elif turma:
            data = attrs.get("data") or getattr(self.instance, "data", None)
            # Sobreposição é checada aqui porque não existe constraint de
            # banco pra interseção de array: sem isto, duas chamadas no
            # mesmo tempo entrariam as duas e a frequência contaria o
            # tempo em dobro.
            candidato = RegistroPresenca(
                pk=getattr(self.instance, "pk", None),
                turma=turma,
                data=data,
                tempos=tempos,
            )
            conflito = tempos_sobrepostos(candidato)
            if conflito:
                lista = ", ".join(f"{ordem}º" for ordem in conflito)
                errors["tempos"] = (
                    f"Já existe chamada desta turma neste dia cobrindo o "
                    f"{lista} tempo."
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
