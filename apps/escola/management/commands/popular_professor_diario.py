"""Cria um professor de teste com lecionamentos COM grade (`dias_semana`).

Pensado pra exercitar o Diário de Aula: sem `dias_semana` preenchido a
agenda não projeta nenhum slot, e ainda não há tela pra editar a grade —
então este seed monta tudo que o fluxo precisa de ponta a ponta:

1. um `Usuario(perfil=professor)` com senha conhecida;
2. o `Professor` vinculado;
3. uma turma e duas disciplinas (reusa as existentes da escola se houver);
4. dois `Lecionamento` com `dias_semana` preenchido (seg/qua e ter/qui).

Idempotente: tudo via get_or_create; rodar de novo não duplica e
re-garante a grade. A senha é sempre redefinida (é usuário de teste).

Uso (dev OU contra o banco de prod via DATABASE_URL local):

    python manage.py popular_professor_diario --escola-id 1

Sem `--escola-id`, usa a primeira escola cadastrada.
"""
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Usuario
from apps.escola.models import (
    Disciplina,
    Escola,
    Lecionamento,
    Professor,
    Turma,
)


class Command(BaseCommand):
    help = "Cria um professor de teste com lecionamentos com grade (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument("--escola-id", type=int, default=None)
        parser.add_argument("--username", type=str, default="prof_diario")
        parser.add_argument("--senha", type=str, default="diario123")
        parser.add_argument("--ano", type=int, default=datetime.now().year)

    @transaction.atomic
    def handle(self, *args, **opts):
        escola = self._resolver_escola(opts["escola_id"])
        usuario = self._garantir_usuario(
            escola=escola,
            username=opts["username"],
            senha=opts["senha"],
        )
        professor = self._garantir_professor(escola=escola, usuario=usuario)
        turma = self._garantir_turma(escola=escola, ano=opts["ano"])
        disciplinas = self._garantir_disciplinas(escola=escola)

        # Grades distintas pra ter variedade de dias no diário.
        grades = [[0, 2], [1, 3]]  # seg/qua e ter/qui
        for disciplina, dias in zip(disciplinas, grades):
            self._garantir_lecionamento(
                escola=escola,
                professor=professor,
                turma=turma,
                disciplina=disciplina,
                dias_semana=dias,
            )

        self.stdout.write(
            self.style.SUCCESS(
                "\nProfessor de teste pronto.\n"
                f"  login:    {opts['username']}\n"
                f"  senha:    {opts['senha']}\n"
                f"  escola:   {escola.nome}\n"
                f"  turma:    {turma.nome} ({turma.ano_letivo})\n"
                f"  vínculos: "
                + ", ".join(d.nome for d in disciplinas)
                + "\nAbra 'Diário de aula' na sidebar pra ver a agenda."
            )
        )

    def _resolver_escola(self, escola_id):
        if escola_id is not None:
            try:
                return Escola.objects.get(pk=escola_id)
            except Escola.DoesNotExist as exc:
                raise CommandError(f"Escola id={escola_id} não encontrada.") from exc
        escola = Escola.objects.order_by("id").first()
        if escola is None:
            raise CommandError("Nenhuma escola cadastrada. Crie uma primeiro.")
        return escola

    def _garantir_usuario(self, *, escola, username, senha):
        usuario, criado = Usuario.objects.get_or_create(
            username=username,
            defaults={
                "perfil": Usuario.Perfil.PROFESSOR,
                "escola": escola,
                "first_name": "Professor",
                "last_name": "Diário",
            },
        )
        # Garante perfil/escola/senha mesmo se o usuário já existia.
        usuario.perfil = Usuario.Perfil.PROFESSOR
        usuario.escola = escola
        usuario.set_password(senha)
        usuario.save()
        self.stdout.write(
            ("  + Usuário" if criado else "  = Usuário") + f" '{username}'."
        )
        return usuario

    def _garantir_professor(self, *, escola, usuario):
        professor, criado = Professor.objects.get_or_create(
            usuario=usuario,
            defaults={"escola": escola, "ativo": True},
        )
        self.stdout.write(("  + Professor" if criado else "  = Professor") + ".")
        return professor

    def _garantir_turma(self, *, escola, ano):
        turma, criada = Turma.objects.get_or_create(
            escola=escola,
            nome="Turma Diário",
            ano_letivo=ano,
            defaults={"turno": Turma.Turno.MATUTINO, "ativa": True},
        )
        self.stdout.write(("  + Turma" if criada else "  = Turma") + " 'Turma Diário'.")
        return turma

    def _garantir_disciplinas(self, *, escola):
        # Reusa as duas primeiras disciplinas ativas; cria fallback se faltar.
        existentes = list(
            Disciplina.objects.filter(escola=escola, ativa=True).order_by("nome")[:2]
        )
        nomes_fallback = ["Matemática", "História"]
        while len(existentes) < 2:
            nome = nomes_fallback[len(existentes)]
            disciplina, _ = Disciplina.objects.get_or_create(
                escola=escola, nome=nome, defaults={"ativa": True}
            )
            if disciplina not in existentes:
                existentes.append(disciplina)
        return existentes[:2]

    def _garantir_lecionamento(self, *, escola, professor, turma, disciplina, dias_semana):
        lecionamento, criado = Lecionamento.objects.get_or_create(
            professor=professor,
            turma=turma,
            disciplina=disciplina,
            defaults={"escola": escola, "ativo": True, "dias_semana": dias_semana},
        )
        # Re-garante a grade mesmo se o vínculo já existia (ex.: criado
        # antes do campo dias_semana existir).
        if lecionamento.dias_semana != dias_semana or not lecionamento.ativo:
            lecionamento.dias_semana = dias_semana
            lecionamento.ativo = True
            lecionamento.save(update_fields=["dias_semana", "ativo"])
        self.stdout.write(
            ("  + Lecionamento " if criado else "  = Lecionamento ")
            + f"{disciplina.nome} (dias {dias_semana})."
        )
        return lecionamento
