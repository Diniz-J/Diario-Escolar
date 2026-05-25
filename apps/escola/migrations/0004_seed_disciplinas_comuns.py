from django.db import migrations

# Lista das disciplinas mais comuns do ensino fundamental (anos finais) e
# do ensino médio, em ordem alfabética. Cobrem o currículo base da BNCC e
# evitam que cada escola precise cadastrar manualmente as matérias usuais.
#
# A migration é idempotente: usa get_or_create por (escola, nome), então
# rodar de novo (ou aplicar em escolas que já tenham parte das matérias)
# não duplica nada e não sobrescreve disciplinas existentes.
DISCIPLINAS_COMUNS = [
    "Arte",
    "Biologia",
    "Ciências",
    "Educação Física",
    "Ensino Religioso",
    "Filosofia",
    "Física",
    "Geografia",
    "História",
    "Língua Inglesa",
    "Língua Portuguesa",
    "Matemática",
    "Química",
    "Sociologia",
]


def seed_disciplinas_comuns(apps, schema_editor):
    """Cria as disciplinas comuns para cada escola já cadastrada.

    Usa o modelo histórico via `apps.get_model` (e não o import direto)
    para que a migration continue funcionando mesmo se o modelo evoluir
    no futuro.
    """
    Escola = apps.get_model("escola", "Escola")
    Disciplina = apps.get_model("escola", "Disciplina")

    for escola in Escola.objects.all():
        for nome in DISCIPLINAS_COMUNS:
            Disciplina.objects.get_or_create(
                escola=escola,
                nome=nome,
                defaults={"ativa": True},
            )


class Migration(migrations.Migration):
    dependencies = [
        ("escola", "0003_professor"),
    ]

    # Sem reverse para não apagar disciplinas em rollback — uma vez
    # cadastradas elas podem estar referenciadas por planos de ensino,
    # tarefas e ocorrências, então deletar é destrutivo demais para um
    # caminho automático.
    operations = [
        migrations.RunPython(
            seed_disciplinas_comuns,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
