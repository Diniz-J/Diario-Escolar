"""Resource de import/export do PlanoEnsino.

Referencia turma e disciplina por **nome** (e ano letivo pra desambiguar
turma). Professor é opcional, também por username quando informado.
Não cria entidades faltantes — turma/disciplina ausente vira erro de
linha (cadastre antes).

Chave natural: `(escola, turma, disciplina, ano_letivo)`.
"""
from __future__ import annotations

from import_export import fields
from import_export.widgets import BooleanWidget, IntegerWidget

from apps.common.import_export import BaseEscolaResource
from apps.escola.models import Disciplina, Professor, Turma
from apps.escola.resources import (
    _disciplina_por_nome,
    _turma_por_nome_ano,
)

from .models import PlanoEnsino


class PlanoEnsinoResource(BaseEscolaResource):
    """Import/export do plano anual de ensino.

    Campos da planilha:
        turma_nome, ano_letivo, disciplina_nome, professor_username,
        ementa, conteudo_programatico, objetivos_gerais,
        objetivos_especificos, habilidades_bncc, carga_horaria,
        metodologia, recursos, avaliacao, ativo
    """

    turma = fields.Field(
        column_name="turma",
        attribute="turma_id",
        widget=IntegerWidget(),
    )
    disciplina = fields.Field(
        column_name="disciplina",
        attribute="disciplina_id",
        widget=IntegerWidget(),
    )
    professor = fields.Field(
        column_name="professor",
        attribute="professor_id",
        widget=IntegerWidget(),
    )
    ativo = fields.Field(
        column_name="ativo",
        attribute="ativo",
        widget=BooleanWidget(),
        default=True,
    )

    class Meta:
        model = PlanoEnsino
        import_id_fields = ("escola", "turma", "disciplina", "ano_letivo")
        fields = (
            "turma",
            "disciplina",
            "professor",
            "ano_letivo",
            "ementa",
            "conteudo_programatico",
            "objetivos_gerais",
            "objetivos_especificos",
            "habilidades_bncc",
            "carga_horaria",
            "metodologia",
            "recursos",
            "avaliacao",
            "ativo",
        )
        export_order = fields

    def export(self, queryset=None, **kwargs):
        """Substitui colunas numéricas pelos nomes legíveis no export."""
        dataset = super().export(queryset=queryset, **kwargs)
        if queryset is None:
            queryset = self.get_queryset()

        turmas = {
            t.id: (t.nome, t.ano_letivo)
            for t in Turma.objects.filter(
                id__in=queryset.values_list("turma_id", flat=True)
            )
        }
        disciplinas = {
            d.id: d.nome
            for d in Disciplina.objects.filter(
                id__in=queryset.values_list("disciplina_id", flat=True)
            )
        }
        professores = {
            p.id: p.usuario.username
            for p in Professor.objects.filter(
                id__in=queryset.values_list("professor_id", flat=True)
            ).select_related("usuario")
        }

        novos_headers = list(dataset.headers)
        # Renomeia colunas numéricas pra "_nome"/"_username".
        renomear = {
            "turma": "turma_nome",
            "disciplina": "disciplina_nome",
            "professor": "professor_username",
        }
        for antigo, novo in renomear.items():
            if antigo in novos_headers:
                novos_headers[novos_headers.index(antigo)] = novo

        novo_dataset = type(dataset)(headers=novos_headers)
        for linha in dataset:
            mapa = dict(zip(dataset.headers, linha))
            try:
                turma_id = int(mapa.get("turma") or 0)
            except (TypeError, ValueError):
                turma_id = 0
            try:
                disc_id = int(mapa.get("disciplina") or 0)
            except (TypeError, ValueError):
                disc_id = 0
            try:
                prof_id = int(mapa.get("professor") or 0)
            except (TypeError, ValueError):
                prof_id = 0
            nome_turma, _ano = turmas.get(turma_id, ("", ""))
            mapa["turma"] = nome_turma
            mapa["disciplina"] = disciplinas.get(disc_id, "")
            mapa["professor"] = professores.get(prof_id, "")
            novo_dataset.append(
                tuple(mapa.get(h.replace("_nome", "").replace("_username", ""), mapa.get(h, "")) for h in novos_headers)
            )
        return novo_dataset

    def before_import_row(self, row, **kwargs):
        super().before_import_row(row, **kwargs)
        escola_id = self.contexto.escola_id if self.contexto else None
        if escola_id is None:
            raise ValueError("Escola não definida no contexto do import.")

        # ano_letivo é obrigatório (chave natural).
        if not row.get("ano_letivo"):
            raise ValueError("Coluna 'ano_letivo' obrigatória.")
        ano = int(row["ano_letivo"])

        # Resolve turma.
        turma_ref = row.get("turma_nome") or row.get("turma") or ""
        turma_ref = str(turma_ref).strip()
        if turma_ref.isdigit():
            row["turma"] = int(turma_ref)
        else:
            if not turma_ref:
                raise ValueError("Coluna 'turma_nome' obrigatória.")
            turma = _turma_por_nome_ano(escola_id, turma_ref, ano)
            if turma is None:
                raise ValueError(
                    f"Turma '{turma_ref}' ({ano}) não existe. Cadastre antes."
                )
            row["turma"] = turma.id

        # Resolve disciplina.
        disc_ref = row.get("disciplina_nome") or row.get("disciplina") or ""
        disc_ref = str(disc_ref).strip()
        if disc_ref.isdigit():
            row["disciplina"] = int(disc_ref)
        else:
            if not disc_ref:
                raise ValueError("Coluna 'disciplina_nome' obrigatória.")
            disc = _disciplina_por_nome(escola_id, disc_ref)
            if disc is None:
                raise ValueError(
                    f"Disciplina '{disc_ref}' não existe. Cadastre antes."
                )
            row["disciplina"] = disc.id

        # Resolve professor (opcional — fica vazio se não informado).
        prof_ref = (
            row.get("professor_username") or row.get("professor") or ""
        )
        prof_ref = str(prof_ref).strip()
        if not prof_ref:
            # `professor` é nullable em PlanoEnsino — deixa vazio mesmo.
            row["professor"] = ""
        elif prof_ref.isdigit():
            row["professor"] = int(prof_ref)
        else:
            prof = (
                Professor.objects.filter(
                    usuario__username=prof_ref, escola_id=escola_id
                )
                .first()
            )
            if prof is None:
                raise ValueError(
                    f"Professor '{prof_ref}' não existe nesta escola."
                )
            row["professor"] = prof.id

    def _descricao_linha(self, row) -> str:
        turma = row.get("turma_nome") or row.get("turma") or "?"
        disc = row.get("disciplina_nome") or row.get("disciplina") or "?"
        return f"{disc} em {turma} ({row.get('ano_letivo', '?')})"
