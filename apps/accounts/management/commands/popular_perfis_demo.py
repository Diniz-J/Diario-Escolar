"""Cria um usuário de teste para cada perfil de nível administrativo/leitura.

Pensado pra exercitar a UI por papel (sidebar, labels, gates de permissão)
sem montar cada usuário na mão. Cria um de cada:

- diretor
- secretaria  (alias de diretor)
- coordenador (alias de diretor)
- inspetor    (alias de professor)

Todos vinculados a uma escola (a primeira cadastrada, ou `--escola-id`).
NÃO cria professor (perfil `professor` tem seed próprio: popular_professor_diario).

Idempotente: get_or_create por username; rodar de novo não duplica e
re-garante perfil/escola. A senha é sempre redefinida (são usuários de teste).

ATENÇÃO: o perfil `coordenador` só é aceito por backends que já tenham a
migration 0005 (enum atualizado). Em ambiente desatualizado o create do
coordenador falha na validação do choice — rode após o deploy do branch.

Uso:

    python manage.py popular_perfis_demo --escola-id 1

Sem `--escola-id`, usa a primeira escola cadastrada.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Usuario
from apps.escola.models import Escola

# (perfil, username, senha, first_name) — last_name é fixo "Demo".
_PERFIS = [
    (Usuario.Perfil.DIRETOR, "demo_diretor", "diretor123", "Diretor"),
    (Usuario.Perfil.SECRETARIA, "demo_secretaria", "secretaria123", "Secretaria"),
    (Usuario.Perfil.COORDENADOR, "demo_coordenador", "coordenador123", "Coordenador"),
    (Usuario.Perfil.INSPETOR, "demo_inspetor", "inspetor123", "Inspetor"),
]


class Command(BaseCommand):
    help = "Cria um usuário de teste para cada perfil (diretor/secretaria/coordenador/inspetor)."

    def add_arguments(self, parser):
        parser.add_argument("--escola-id", type=int, default=None)

    def handle(self, *args, **opts):
        escola = self._resolver_escola(opts["escola_id"])
        self.stdout.write(f"Escola: {escola.nome} (id={escola.id})\n")

        for perfil, username, senha, first_name in _PERFIS:
            usuario, criado = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    "perfil": perfil,
                    "escola": escola,
                    "first_name": first_name,
                    "last_name": "Demo",
                },
            )
            # Re-garante perfil/escola/senha mesmo se o usuário já existia.
            usuario.perfil = perfil
            usuario.escola = escola
            usuario.set_password(senha)
            usuario.save()
            marca = "+" if criado else "="
            self.stdout.write(
                f"  {marca} {perfil:12} login={username:18} senha={senha}"
            )

        self.stdout.write(
            self.style.SUCCESS("\nPerfis de teste prontos.")
        )

    def _resolver_escola(self, escola_id):
        if escola_id is not None:
            try:
                return Escola.objects.get(pk=escola_id)
            except Escola.DoesNotExist as exc:
                raise CommandError(
                    f"Escola id={escola_id} não encontrada."
                ) from exc
        escola = Escola.objects.order_by("id").first()
        if escola is None:
            raise CommandError("Nenhuma escola cadastrada. Crie uma primeiro.")
        return escola
