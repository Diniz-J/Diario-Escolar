"""Serviços da app grade — clonagem da grade de uma turma pra outra.

Existe porque a grade é por turma, e `Turma` é por ano letivo: a virada
de ano significa remontar a semana inteira de cada turma à mão. Clonar da
turma equivalente do ano anterior é o que torna a realocação anual
suportável (ver `PRESENCA.md` §2.1 — a grade é editável justamente porque
o registro de presença não depende dela).

Duas decisões que não se deduzem do código:

**O mapeamento é por `(professor, disciplina)`, não por id de
lecionamento.** O lecionamento da origem é de outra turma, então não
serve: o que se quer é "quem dava esta matéria continua dando". Slot cujo
par não tem lecionamento ativo na turma destino é **ignorado e
reportado**, nunca criado pela metade — professor que saiu da escola é o
caso comum, e criar o slot sem vínculo violaria a invariante do modelo.

**O tempo é remapeado por `ordem` dentro do turno da turma destino**, e
não copiado por id. Turma de manhã clonada pra uma de tarde usa o 2º
tempo do vespertino, não o horário do matutino — que o `clean()` recusaria
por turno divergente.
"""
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from simple_history.utils import bulk_create_with_history

from apps.escola.models import Lecionamento, Turma

from .models import AulaGrade, TempoAula


@dataclass
class ResultadoClonagem:
    """Quantos slots entraram e quais foram deixados de fora, com o motivo."""

    criados: int = 0
    ignorados: list[dict] = field(default_factory=list)


def clonar_grade(*, origem: Turma, destino: Turma) -> ResultadoClonagem:
    """Copia os slots ativos de `origem` pra `destino`.

    Exige a turma destino sem grade ativa: clonar sobre uma grade montada
    duplicaria horário ou esbarraria no unique parcial no meio do lote,
    e "o que já estava lá" não é decisão do clone.
    """
    if origem.escola_id != destino.escola_id:
        raise ValidationError(
            {"turma_origem": "As duas turmas devem ser da mesma escola."}
        )
    if origem.pk == destino.pk:
        raise ValidationError(
            {"turma_destino": "A turma destino deve ser diferente da origem."}
        )

    # Trava a turma destino e revalida "sem grade ativa" dentro da mesma
    # transação pra que dois POSTs concorrentes não passem ambos pelo check
    # e depois caiam no unique parcial como IntegrityError (500).
    with transaction.atomic():
        Turma.objects.select_for_update().filter(pk=destino.pk).first()
        if AulaGrade.objects.filter(turma=destino, ativo=True).exists():
            raise ValidationError(
                {
                    "turma_destino": (
                        "A turma destino já tem grade montada. Remova os horários "
                        "existentes antes de clonar."
                    )
                }
            )

        slots_origem = list(
            AulaGrade.objects.filter(turma=origem, ativo=True).select_related(
                "tempo", "lecionamento"
            )
        )
        resultado = ResultadoClonagem()
        if not slots_origem:
            return resultado

        # Lecionamentos ativos do destino, indexados por (professor, disciplina)
        # — é o par que significa "quem dá esta matéria nesta turma". Se o
        # mesmo par aparecer em mais de um lecionamento ativo (invariante que
        # o modelo não garante hoje), `setdefault` + `order_by("id")` fixa o
        # de menor id, pra o clone não depender da ordem do ORM.
        lecionamentos: dict[tuple[int, int], Lecionamento] = {}
        for lec in Lecionamento.objects.filter(
            turma=destino, ativo=True
        ).order_by("id"):
            lecionamentos.setdefault((lec.professor_id, lec.disciplina_id), lec)
        # Tempos do turno do destino, indexados por ordem.
        tempos = {
            tempo.ordem: tempo
            for tempo in TempoAula.objects.filter(
                escola_id=destino.escola_id, turno=destino.turno, ativo=True
            )
        }

        novos: list[AulaGrade] = []
        for slot in slots_origem:
            chave = (
                slot.lecionamento.professor_id,
                slot.lecionamento.disciplina_id,
            )
            lecionamento = lecionamentos.get(chave)
            tempo = tempos.get(slot.tempo.ordem)

            if lecionamento is None:
                resultado.ignorados.append(
                    {
                        "dia_semana": slot.dia_semana,
                        "tempo_ordem": slot.tempo.ordem,
                        "motivo": (
                            "Não há lecionamento ativo deste professor para esta "
                            "disciplina na turma destino."
                        ),
                    }
                )
                continue
            if tempo is None:
                resultado.ignorados.append(
                    {
                        "dia_semana": slot.dia_semana,
                        "tempo_ordem": slot.tempo.ordem,
                        "motivo": (
                            f"A turma destino não tem {slot.tempo.ordem}º tempo "
                            "cadastrado no turno dela."
                        ),
                    }
                )
                continue

            novos.append(
                AulaGrade(
                    escola_id=destino.escola_id,
                    lecionamento=lecionamento,
                    turma=destino,
                    dia_semana=slot.dia_semana,
                    tempo=tempo,
                )
            )

        if novos:
            try:
                bulk_create_with_history(novos, AulaGrade)
            except IntegrityError as exc:
                # Caiu no unique parcial — outro POST concorrente venceu a
                # corrida depois do nosso check. Traduz pra 400 em vez de 500.
                raise ValidationError(
                    {
                        "turma_destino": (
                            "Outro clone concorrente já criou slots nessa turma; "
                            "recarregue e tente de novo."
                        )
                    }
                ) from exc
        resultado.criados = len(novos)
        return resultado
