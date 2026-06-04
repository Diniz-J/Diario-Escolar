from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("escola", "0007_historicalaluno_historicallecionamento_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="escola",
            name="importacao_em_lote_habilitada",
            field=models.BooleanField(default=False),
        ),
    ]
