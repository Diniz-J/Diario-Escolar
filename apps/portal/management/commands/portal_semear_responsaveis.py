"""Cria `Responsavel` e os vínculos a partir dos dados já no cadastro do aluno.

A escola já digitou `nome_responsavel` e `email_responsavel` em cada aluno
— o portal não pode exigir que ela redigite tudo. Este comando converte
esses campos nas contas e nos vínculos do portal.

**Idempotente**: tudo via `get_or_create`. Rodar de novo não duplica,
apenas completa o que faltar (aluno novo matriculado depois, por exemplo).

**Deduplica por email.** Irmãos na mesma escola compartilham o email do
responsável: viram **uma** conta com **dois** vínculos. Sem isso o pai de
dois filhos teria duas contas e dois convites.

**Aluno sem email de responsável é pulado, de propósito.** O email é a
âncora da identidade: é por ele que o convite sai e é com ele que o
responsável loga. Criar uma conta sem email produziria uma linha que não
dá pra convidar nem autenticar — e como boa parte desses alunos também
está sem `nome_responsavel` (os de seed mock vêm com os dois vazios), o
resultado seria uma pilha de registros anônimos e inúteis. Quem está sem
email já aparece como tal na listagem de alunos e no log de entrega dos
comunicados; duplicar essa informação aqui não ajudaria ninguém. Quando a
escola preencher o email no aluno, basta rodar o comando de novo.

**Inclui aluno inativo.** Decisão registrada no `PORTAL.md`: desativar o
aluno (transferência) não corta o acesso do responsável ao histórico; ele
só para de receber comunicado novo.

A conta nasce **sem senha utilizável** — ninguém entra no portal sem
passar pelo convite (fatia 3).

Uso:

    python manage.py portal_semear_responsaveis
    python manage.py portal_semear_responsaveis --escola-id 1
    python manage.py portal_semear_responsaveis --dry-run
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.escola.models import Aluno
from apps.portal.models import Responsavel, ResponsavelAluno, normalizar_email

NOME_PADRAO = "Responsável"


class Command(BaseCommand):
    help = "Cria responsáveis e vínculos a partir do cadastro dos alunos (idempotente)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--escola-id",
            type=int,
            default=None,
            help="Limita a uma escola. Default: todas.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Só relata o que faria, sem gravar nada.",
        )

    def handle(self, *args, **options) -> None:
        escola_id = options["escola_id"]
        dry_run = options["dry_run"]

        alunos = Aluno.objects.all().order_by("escola_id", "nome_completo")
        if escola_id is not None:
            alunos = alunos.filter(escola_id=escola_id)

        # Agrupa por (escola, email normalizado). A chave é o par porque o
        # unique do model é por escola: o mesmo email em duas escolas são
        # duas contas distintas, e isso é proposital enquanto a tenancy
        # for por escola.
        grupos: dict[tuple[int, str], dict] = {}
        pulados = 0
        for aluno in alunos.only(
            "id", "escola_id", "nome_completo", "nome_responsavel", "email_responsavel"
        ):
            email = normalizar_email(aluno.email_responsavel)
            if not email:
                pulados += 1
                continue
            grupo = grupos.setdefault(
                (aluno.escola_id, email), {"nome": "", "alunos": []}
            )
            grupo["alunos"].append(aluno)
            if not grupo["nome"] and aluno.nome_responsavel.strip():
                grupo["nome"] = aluno.nome_responsavel.strip()

        if dry_run:
            self.stdout.write(
                f"[dry-run] {len(grupos)} responsáveis para "
                f"{sum(len(g['alunos']) for g in grupos.values())} alunos; "
                f"{pulados} alunos sem email de responsável seriam pulados."
            )
            for (esc, email), grupo in sorted(grupos.items()):
                nomes = ", ".join(a.nome_completo for a in grupo["alunos"])
                self.stdout.write(
                    f"  escola {esc} · {email} ({grupo['nome'] or NOME_PADRAO}) → {nomes}"
                )
            return

        criados_resp = 0
        criados_vinc = 0
        with transaction.atomic():
            for (esc_id, email), grupo in grupos.items():
                responsavel, criado = Responsavel.objects.get_or_create(
                    escola_id=esc_id,
                    email=email,
                    defaults={"nome": grupo["nome"] or NOME_PADRAO},
                )
                if criado:
                    # Sem senha utilizável: o acesso só nasce pelo convite.
                    responsavel.set_unusable_password()
                    responsavel.save(update_fields=["password"])
                    criados_resp += 1

                for aluno in grupo["alunos"]:
                    _vinculo, vinc_criado = ResponsavelAluno.objects.get_or_create(
                        responsavel=responsavel, aluno=aluno
                    )
                    if vinc_criado:
                        criados_vinc += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{criados_resp} responsáveis criados, "
                f"{criados_vinc} vínculos criados. "
                f"{pulados} alunos sem email de responsável foram pulados."
            )
        )
