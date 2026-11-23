"""Cria um professor de teste com grade horária montada.

Pensado pra exercitar o Diário de Aula e a chamada por tempo: sem grade a
agenda não projeta nenhum slot e a chamada não sugere tempo nenhum, então
este seed monta tudo que o fluxo precisa de ponta a ponta:

1. um `Usuario(perfil=professor)` com senha conhecida;
2. o `Professor` vinculado;
3. uma turma e duas disciplinas (reusa as existentes da escola se houver);
4. quatro `TempoAula` no turno da turma (o catálogo de horários);
5. dois `Lecionamento` com slots de `AulaGrade` (seg/qua e ter/qui).

A fonte dos dias era `Lecionamento.dias_semana`, removido em nov/2026 —
agora quem diz é a grade (`apps.grade`, fatia 5 do `PRESENCA.md`). Já
existe tela pra editar a grade (`/grade`), então este comando deixou de
ser o único caminho; segue útil pra popular ambiente novo de uma vez.

Idempotente: tudo via get_or_create; rodar de novo não duplica e
re-garante a grade. A senha é sempre redefinida (é usuário de teste).

Uso (dev OU contra o banco de prod via DATABASE_URL local):

    python manage.py popular_professor_diario --escola-id 1

Sem `--escola-id`, usa a primeira escola cadastrada.
"""
from datetime import datetime, time

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
from apps.grade.models import AulaGrade, TempoAula


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
        tempos = self._garantir_tempos(escola=escola, turma=turma)

        # Dias distintos pra ter variedade no diário, e dois tempos
        # seguidos em cada um — é o bloco duplo que a chamada por tempo
        # existe pra representar.
        grades = [[0, 2], [1, 3]]  # seg/qua e ter/qui
        for indice, (disciplina, dias) in enumerate(zip(disciplinas, grades)):
            lecionamento = self._garantir_lecionamento(
                escola=escola,
                professor=professor,
                turma=turma,
                disciplina=disciplina,
            )
            # Primeira disciplina no 1º/2º tempo, segunda no 3º/4º.
            do_bloco = tempos[indice * 2 : indice * 2 + 2]
            self._garantir_slots(
                escola=escola,
                lecionamento=lecionamento,
                turma=turma,
                dias=dias,
                tempos=do_bloco,
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

    def _garantir_tempos(self, *, escola, turma):
        """Catálogo de quatro tempos de 50 minutos no turno da turma."""
        tempos = []
        for ordem in range(1, 5):
            inicio = time(6 + ordem, 0)
            fim = time(6 + ordem, 50)
            tempo, criado = TempoAula.objects.get_or_create(
                escola=escola,
                turno=turma.turno,
                ordem=ordem,
                defaults={"hora_inicio": inicio, "hora_fim": fim, "ativo": True},
            )
            tempos.append(tempo)
            self.stdout.write(
                ("  + Tempo " if criado else "  = Tempo ")
                + f"{ordem}º ({tempo.hora_inicio:%H:%M}-{tempo.hora_fim:%H:%M})."
            )
        return tempos

    def _garantir_lecionamento(self, *, escola, professor, turma, disciplina):
        lecionamento, criado = Lecionamento.objects.get_or_create(
            professor=professor,
            turma=turma,
            disciplina=disciplina,
            defaults={"escola": escola, "ativo": True},
        )
        if not lecionamento.ativo:
            lecionamento.ativo = True
            lecionamento.save(update_fields=["ativo"])
        self.stdout.write(
            ("  + Lecionamento " if criado else "  = Lecionamento ")
            + f"{disciplina.nome}."
        )
        return lecionamento

    def _garantir_slots(self, *, escola, lecionamento, turma, dias, tempos):
        """Põe o lecionamento na grade nos dias e tempos informados."""
        for dia in dias:
            for tempo in tempos:
                _, criado = AulaGrade.objects.get_or_create(
                    escola=escola,
                    turma=turma,
                    dia_semana=dia,
                    tempo=tempo,
                    defaults={"lecionamento": lecionamento, "ativo": True},
                )
                self.stdout.write(
                    ("    + Grade " if criado else "    = Grade ")
                    + f"dia {dia}, {tempo.ordem}º tempo."
                )
