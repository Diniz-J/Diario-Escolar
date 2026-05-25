"""Serializers da app tarefas."""
from datetime import date

from rest_framework import serializers

from .models import EntregaTarefa, Tarefa


class TarefaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tarefa
        fields = [
            "id",
            "escola",
            "turma",
            "disciplina",
            "professor",
            "titulo",
            "descricao",
            "data_lancamento",
            "prazo",
            "vale_nota",
            "nota_maxima",
            "peso",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]

    def validate_escola(self, value):
        """Recusa payload com `escola` diferente da do usuário autenticado.

        Mesmo guard de IDOR aplicado em `ocorrencias` e `presenca`:
        admin/superuser pulam.
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
                "Você só pode lançar tarefas na sua própria escola."
            )
        return value

    def validate(self, attrs: dict) -> dict:
        """Espelha invariantes cruzadas de `Tarefa.clean()`.

        Tratamento de PATCH parcial: campos ausentes do payload puxam do
        `self.instance` antes de validar.
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
        data_lancamento = attrs.get("data_lancamento") or getattr(
            self.instance, "data_lancamento", None
        )
        prazo = attrs.get("prazo")
        if prazo is None and self.instance is not None and "prazo" not in attrs:
            prazo = self.instance.prazo
        vale_nota = attrs.get(
            "vale_nota",
            getattr(self.instance, "vale_nota", False),
        )
        nota_maxima = attrs.get(
            "nota_maxima",
            getattr(self.instance, "nota_maxima", None),
        )

        errors: dict[str, str] = {}

        if turma and escola and turma.escola_id != escola.id:
            errors["turma"] = "A turma deve pertencer à mesma escola da tarefa."

        if disciplina and escola and disciplina.escola_id != escola.id:
            errors["disciplina"] = (
                "A disciplina deve pertencer à mesma escola da tarefa."
            )

        if professor and escola and professor.escola_id != escola.id:
            errors["professor"] = (
                "O professor deve pertencer à mesma escola da tarefa."
            )

        if prazo and data_lancamento and prazo < data_lancamento:
            errors["prazo"] = (
                "O prazo não pode ser anterior à data de lançamento."
            )

        if vale_nota and (nota_maxima is None or nota_maxima <= 0):
            errors["nota_maxima"] = (
                "Tarefa que vale nota precisa de nota máxima maior que zero."
            )

        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class EntregaTarefaSerializer(serializers.ModelSerializer):
    """Serializer de `EntregaTarefa`.

    `escola` é derivado de `tarefa.escola` no save() do model — fora dos
    campos editáveis. `tarefa` e `aluno` são fixados na auto-geração e
    permanecem read-only.
    """

    status = serializers.SerializerMethodField()

    class Meta:
        model = EntregaTarefa
        fields = [
            "id",
            "tarefa",
            "aluno",
            "entregue",
            "data_entrega",
            "nota",
            "observacao",
            "status",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = [
            "id",
            "tarefa",
            "aluno",
            "status",
            "criado_em",
            "atualizado_em",
        ]

    def get_status(self, obj: EntregaTarefa) -> str:
        return obj.status

    def validate(self, attrs: dict) -> dict:
        """Aplica regras de nota e mantém coerência entregue/data_entrega.

        - Quando `entregue=True` sem `data_entrega` no payload, usa hoje.
        - Quando `entregue=False`, limpa `data_entrega` e `nota` (não
          faz sentido marcar entrega que não existe).
        - Nota é rejeitada se a tarefa não vale nota ou excede a máxima.
        """
        instance = self.instance
        entregue = attrs.get(
            "entregue", getattr(instance, "entregue", False)
        )
        data_entrega = attrs.get("data_entrega")
        if (
            data_entrega is None
            and instance is not None
            and "data_entrega" not in attrs
        ):
            data_entrega = instance.data_entrega
        nota = attrs.get("nota")
        if nota is None and instance is not None and "nota" not in attrs:
            nota = instance.nota
        tarefa = instance.tarefa if instance else None

        errors: dict[str, str] = {}

        if entregue and not data_entrega:
            # Auto-preenche `data_entrega` ao marcar entregue sem data.
            attrs["data_entrega"] = date.today()
        if not entregue:
            attrs["data_entrega"] = None
            attrs["nota"] = None

        if nota is not None and tarefa is not None:
            if not tarefa.vale_nota:
                errors["nota"] = (
                    "Esta tarefa não vale nota; o campo deve ficar vazio."
                )
            elif (
                tarefa.nota_maxima is not None and nota > tarefa.nota_maxima
            ):
                errors["nota"] = (
                    f"A nota não pode ser maior que {tarefa.nota_maxima}."
                )

        if errors:
            raise serializers.ValidationError(errors)
        return attrs
