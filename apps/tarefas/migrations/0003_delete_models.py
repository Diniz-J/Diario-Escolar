"""Drop final dos modelos `Tarefa` e `EntregaTarefa`.

A app `tarefas` foi substituída por `avaliacao` (PR #72). Os dados
foram migrados em `avaliacao.0003_migrar_tarefas`:
- `Tarefa(vale_nota=True)` virou `Avaliacao`.
- `EntregaTarefa` correspondente virou `NotaAvaliacao`.
- `Tarefa(vale_nota=False)` foi descartada (decisão do produto).

Esta migration dropa as tabelas do banco. A app `apps.tarefas` continua
registrada em `INSTALLED_APPS` apenas pra preservar a referência das
migrations históricas — Django precisa do app pra resolver
`apps.get_model("tarefas", "Tarefa")` que a `avaliacao.0003` usa
durante seu run.

Ordem dos deletes:
1. Históricos do simple_history (sem FK entre eles).
2. `EntregaTarefa` (filho, tem FK pra Tarefa).
3. `Tarefa` (pai).
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tarefas", "0002_historicalentregatarefa_historicaltarefa"),
        # Garante que a migração de dados já rodou antes da gente
        # apagar as tabelas — sem essa ordem, a `avaliacao.0003` pode
        # tentar ler Tarefas que já foram dropadas em banco fresh.
        ("avaliacao", "0003_migrar_tarefas"),
    ]

    operations = [
        migrations.DeleteModel(name="HistoricalEntregaTarefa"),
        migrations.DeleteModel(name="HistoricalTarefa"),
        migrations.DeleteModel(name="EntregaTarefa"),
        migrations.DeleteModel(name="Tarefa"),
    ]
