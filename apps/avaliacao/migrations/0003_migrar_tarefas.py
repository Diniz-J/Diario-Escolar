"""Migra Tarefa → Avaliacao + EntregaTarefa → NotaAvaliacao.

Critério (decidido com Diniz na sessão 2026-06-05):
- `Tarefa(vale_nota=True)` cuja `data_lancamento` cai em algum
  `PeriodoAvaliativo` cadastrado da escola+ano vira `Avaliacao`. As
  `EntregaTarefa` filhas viram `NotaAvaliacao` (preservando a `nota`
  quando lançada). `tipo` default = 'prova'.
- `Tarefa(vale_nota=False)` ou sem período coberto → **descartada**
  (não cria Avaliacao). EntregaTarefa filhas idem. Diniz: "pode matar
  as tarefas abertas".
- O log conta quantas foram migradas e quantas descartadas.

Operação reversível só dropando as Avaliações criadas — o reverse
desta migration limpa pelo timestamp da criação (criadas durante a
migration têm o mesmo timestamp). Em produção, conservador: não
implementamos reverse (deixar como no-op) pra evitar perda acidental.
"""
from decimal import Decimal

from django.db import migrations


def migrar(apps, schema_editor):
    Tarefa = apps.get_model("tarefas", "Tarefa")
    Avaliacao = apps.get_model("avaliacao", "Avaliacao")
    NotaAvaliacao = apps.get_model("avaliacao", "NotaAvaliacao")
    PeriodoAvaliativo = apps.get_model("avaliacao", "PeriodoAvaliativo")

    migradas = 0
    descartadas_sem_periodo = 0
    descartadas_sem_nota = 0

    # `select_related` reduz N+1 quando iteramos a tabela inteira.
    tarefas = (
        Tarefa.objects.select_related("turma", "disciplina", "escola")
        .all()
    )

    for tarefa in tarefas:
        if not tarefa.vale_nota:
            descartadas_sem_nota += 1
            continue

        ano = tarefa.turma.ano_letivo
        periodo = (
            PeriodoAvaliativo.objects.filter(
                escola_id=tarefa.escola_id,
                ano_letivo=ano,
                data_inicio__lte=tarefa.data_lancamento,
                data_fim__gte=tarefa.data_lancamento,
                ativo=True,
            )
            .order_by("ordem")
            .first()
        )
        if periodo is None:
            descartadas_sem_periodo += 1
            continue

        avaliacao = Avaliacao.objects.create(
            escola_id=tarefa.escola_id,
            turma_id=tarefa.turma_id,
            disciplina_id=tarefa.disciplina_id,
            professor_id=tarefa.professor_id,
            periodo_id=periodo.id,
            titulo=tarefa.titulo,
            descricao=tarefa.descricao,
            tipo="prova",  # default mais provável pra avaliações antigas
            data=tarefa.data_lancamento,
            nota_maxima=tarefa.nota_maxima or Decimal("10"),
            peso=tarefa.peso,
            ativo=True,
        )

        # EntregaTarefa → NotaAvaliacao (uma por aluno).
        # `related_name="entregas"` em Tarefa.
        for entrega in tarefa.entregas.all():
            NotaAvaliacao.objects.create(
                escola_id=avaliacao.escola_id,
                avaliacao_id=avaliacao.id,
                aluno_id=entrega.aluno_id,
                nota=entrega.nota,
                observacao=entrega.observacao or "",
            )

        migradas += 1

    # Mensagem visível no output do migrate — útil pra confirmar que a
    # migração rodou como esperado.
    if migradas or descartadas_sem_periodo or descartadas_sem_nota:
        print(
            f"  [migrar_tarefas] migradas={migradas} "
            f"descartadas_sem_periodo={descartadas_sem_periodo} "
            f"descartadas_sem_nota={descartadas_sem_nota}"
        )


def reverter(apps, schema_editor):
    """No-op intencional.

    Reverter implicaria deletar Avaliacao/NotaAvaliacao criadas — em
    produção isso seria perda de dado se o usuário já tiver lançado
    notas em cima. Pra rollback, recriar Tarefa do dump anterior.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("avaliacao", "0002_avaliacao_historicalavaliacao_and_more"),
        ("tarefas", "0002_historicalentregatarefa_historicaltarefa"),
    ]

    operations = [
        migrations.RunPython(migrar, reverter),
    ]
