"""Marca como "sem senha" os responsáveis gravados com senha vazia.

Pelo admin o campo de senha é só leitura, então a conta nascia com `""` —
que o Django trata como senha *utilizável*: o convite recusava ("já ativou"),
o lote pulava e o login nunca passava. O `Responsavel.save()` passou a
corrigir isso, mas só vale pro próximo save; esta migration conserta as
linhas que já estão no banco.

Idempotente: sem linha com senha vazia, não faz nada. `make_password(None)`
porque o modelo histórico da migration não tem `set_unusable_password`.
"""
from django.contrib.auth.hashers import make_password
from django.db import migrations


def marcar_sem_senha(apps, schema_editor):
    Responsavel = apps.get_model("portal", "Responsavel")
    for responsavel in Responsavel.objects.filter(password=""):
        # Um hash inutilizável por linha, como o `set_unusable_password` faz.
        responsavel.password = make_password(None)
        responsavel.save(update_fields=["password"])


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0002_convite_responsavel"),
    ]

    operations = [
        migrations.RunPython(marcar_sem_senha, migrations.RunPython.noop),
    ]
