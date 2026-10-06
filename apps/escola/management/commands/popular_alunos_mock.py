"""Cria uma turma e N alunos mock pra exercitar a UI (paginação, listagem).

Idempotente: a turma e os alunos são criados via `get_or_create`. Rodar de
novo não duplica nada — apenas completa o que faltar pra chegar na meta.

Uso típico (dev ou contra banco de prod via DATABASE_URL local):

    python manage.py popular_alunos_mock \
        --escola-id 1 \
        --turma "Mock 35" \
        --quantidade 35

Sem `--escola-id` usa a primeira escola cadastrada (atalho pra dev).
"""
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.escola.models import Aluno, Escola, Turma


class Command(BaseCommand):
    help = "Cria uma turma e N alunos mock (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--escola-id",
            type=int,
            default=None,
            help="ID da escola. Default: primeira escola cadastrada.",
        )
        parser.add_argument(
            "--turma",
            type=str,
            default="Mock 35",
            help='Nome da turma. Default: "Mock 35".',
        )
        parser.add_argument(
            "--turno",
            type=str,
            default=Turma.Turno.MATUTINO,
            choices=[t for t, _ in Turma.Turno.choices],
            help='Turno da turma. Default: "matutino".',
        )
        parser.add_argument(
            "--ano",
            type=int,
            default=datetime.now().year,
            help="Ano letivo. Default: ano corrente.",
        )
        parser.add_argument(
            "--quantidade",
            type=int,
            default=35,
            help="Quantos alunos criar. Default: 35.",
        )
        parser.add_argument(
            "--prefixo-matricula",
            type=str,
            default="M",
            help='Prefixo da matrícula. Default: "M". '
            'Gera "M001", "M002", ...',
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        escola = self._resolver_escola(opts["escola_id"])
        turma = self._garantir_turma(
            escola=escola,
            nome=opts["turma"],
            turno=opts["turno"],
            ano_letivo=opts["ano"],
        )
        criados = self._garantir_alunos(
            escola=escola,
            turma=turma,
            quantidade=opts["quantidade"],
            prefixo=opts["prefixo_matricula"],
        )

        total = turma.alunos.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Turma '{turma.nome}' ({turma.ano_letivo}, escola "
                f"{escola.nome}) — {criados} alunos novos. Total na turma: "
                f"{total}."
            )
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
            raise CommandError(
                "Nenhuma escola cadastrada. Crie uma primeiro pelo admin."
            )
        return escola

    def _garantir_turma(self, *, escola, nome, turno, ano_letivo):
        turma, criada = Turma.objects.get_or_create(
            escola=escola,
            nome=nome,
            ano_letivo=ano_letivo,
            defaults={"turno": turno, "ativa": True},
        )
        if criada:
            self.stdout.write(f"  + Turma '{nome}' criada.")
        else:
            self.stdout.write(f"  = Turma '{nome}' já existia.")
        return turma

    def _garantir_alunos(self, *, escola, turma, quantidade, prefixo):
        criados = 0
        for i in range(1, quantidade + 1):
            matricula = f"{prefixo}{i:03d}"
            # Largura 03 cobre 1..999. Caso queira N maior, alterar aqui.
            nome = f"Aluno Mock {i:02d}"
            _aluno, criado = Aluno.objects.get_or_create(
                escola=escola,
                matricula=matricula,
                defaults={
                    "nome_completo": nome,
                    "turma": turma,
                    "ativo": True,
                    # Sem responsável / email — campos blank no banco. Ocorrências
                    # criadas pra esses alunos pulam o envio de email (warning
                    # no log e segue).
                    "nome_responsavel": "",
                    "email_responsavel": "",
                },
            )
            if criado:
                criados += 1
        return criados
