"""Resources de import/export da app escola.

Cinco modelos cobertos: Turma, Disciplina, Aluno, Professor, Lecionamento.
Todos herdam de `BaseEscolaResource` (escopo de escola + dedup natural).

Mapeamento de FK por **nome** em vez de id é a peça crítica: planilhas
vindas de fora não conhecem nossos ids. Implementado via:
- `_resolver_*` helpers que rodam em `before_import_row` antes da
  validação do resource, substituindo o nome pelo id resolvido.
- Turmas faltantes são criadas na hora (com defaults do contexto)
  durante o import de Aluno e Lecionamento.

Professor é o caso especial: cria `Usuario` junto + dispara email de
reset de senha. Replica o que o ProfessorFormDialog do front faz quando
o admin cadastra manualmente.
"""
from __future__ import annotations

import logging
import secrets

from django.db import transaction
from import_export import fields
from import_export.widgets import BooleanWidget, IntegerWidget

from apps.accounts.models import PasswordResetToken, Usuario
from apps.accounts.services import enviar_link_redefinicao
from apps.common.import_export import BaseEscolaResource

from .models import Aluno, Disciplina, Lecionamento, Professor, Turma

logger = logging.getLogger(__name__)


# Valores válidos do enum `Turma.Turno`. Aceitamos tanto a chave técnica
# ("matutino") quanto o label PT-BR ("Matutino") no import — escolas
# podem ter planilhas escritas das duas formas.
TURNOS_VALIDOS = {turno.value for turno in Turma.Turno}
TURNOS_LABEL_PARA_VALOR = {
    turno.label.lower(): turno.value for turno in Turma.Turno
}


def _normalizar_turno(valor: str | None, default: str | None = None) -> str:
    """Resolve um valor de turno (chave ou label) pro valor canônico do enum."""
    if not valor and default:
        return default
    if not valor:
        raise ValueError(
            "Turno obrigatório. Use matutino, vespertino, noturno ou integral."
        )
    norm = str(valor).strip().lower()
    if norm in TURNOS_VALIDOS:
        return norm
    if norm in TURNOS_LABEL_PARA_VALOR:
        return TURNOS_LABEL_PARA_VALOR[norm]
    raise ValueError(
        f"Turno inválido: '{valor}'. "
        "Use matutino, vespertino, noturno ou integral."
    )


def _turma_por_nome_ano(
    escola_id: int, nome: str, ano_letivo: int
) -> Turma | None:
    """Busca turma pela chave natural `(escola, nome, ano_letivo)`."""
    return Turma.objects.filter(
        escola_id=escola_id,
        nome=nome,
        ano_letivo=ano_letivo,
    ).first()


def _disciplina_por_nome(escola_id: int, nome: str) -> Disciplina | None:
    return Disciplina.objects.filter(
        escola_id=escola_id, nome=nome
    ).first()


# ===================================================================== #
# Turma                                                                  #
# ===================================================================== #


class TurmaResource(BaseEscolaResource):
    """Import/export de Turma.

    Chave natural: `(escola, nome, ano_letivo)` — duplicado é pulado.
    """

    ativa = fields.Field(
        column_name="ativa",
        attribute="ativa",
        widget=BooleanWidget(),
        default=True,
    )

    class Meta:
        model = Turma
        # `import_id_fields` informa ao django-import-export quais campos
        # usar pra resolver "esta linha já existe?". Combinado com o
        # `skip_row` do BaseEscolaResource, dá o comportamento "pular
        # duplicados" baseado na chave natural.
        import_id_fields = ("escola", "nome", "ano_letivo")
        fields = ("escola", "nome", "turno", "ano_letivo", "ativa")
        export_order = ("nome", "turno", "ano_letivo", "ativa")

    def before_import_row(self, row, **kwargs):
        super().before_import_row(row, **kwargs)
        if "turno" in row:
            row["turno"] = _normalizar_turno(row.get("turno"))

    def _descricao_linha(self, row) -> str:
        return f"{row.get('nome', '?')} ({row.get('ano_letivo', '?')})"


# ===================================================================== #
# Disciplina                                                             #
# ===================================================================== #


class DisciplinaResource(BaseEscolaResource):
    """Import/export de Disciplina.

    Chave natural: `(escola, nome)`. Útil pra subir a lista BNCC de uma
    escola nova em massa.
    """

    ativa = fields.Field(
        column_name="ativa",
        attribute="ativa",
        widget=BooleanWidget(),
        default=True,
    )

    class Meta:
        model = Disciplina
        import_id_fields = ("escola", "nome")
        fields = ("escola", "nome", "ativa")
        export_order = ("nome", "ativa")

    def _descricao_linha(self, row) -> str:
        return str(row.get("nome", "?"))


# ===================================================================== #
# Aluno                                                                  #
# ===================================================================== #


class AlunoResource(BaseEscolaResource):
    """Import/export de Aluno.

    Coluna `turma` é por **nome** (não id). Se a turma não existir, é
    criada na hora com defaults do `ImportContext.extras`:
        - `turno_padrao` (obrigatório no upload de Aluno)
        - `ano_letivo_padrao` (obrigatório)

    Chave natural: `(escola, matricula)` — duplicado é pulado.
    """

    turma = fields.Field(
        column_name="turma",
        attribute="turma_id",
        widget=IntegerWidget(),
    )
    ativo = fields.Field(
        column_name="ativo",
        attribute="ativo",
        widget=BooleanWidget(),
        default=True,
    )

    class Meta:
        model = Aluno
        import_id_fields = ("escola", "matricula")
        fields = (
            "escola",
            "matricula",
            "nome_completo",
            "data_nascimento",
            "turma",
            "nome_responsavel",
            "email_responsavel",
            "ativo",
        )
        export_order = (
            "matricula",
            "nome_completo",
            "data_nascimento",
            "turma",
            "nome_responsavel",
            "email_responsavel",
            "ativo",
        )

    def export(self, queryset=None, **kwargs):
        """Override do export pra anexar colunas legíveis de turma.

        `super().export()` devolve um `Dataset` já formatado; aqui
        injetamos `turma_nome` e `ano_letivo` em cada linha trocando a
        coluna `turma` (numérica) pelo nome.
        """
        dataset = super().export(queryset=queryset, **kwargs)
        if "turma" not in dataset.headers:
            return dataset

        # Construímos um cache `id → (nome, ano_letivo)` pra evitar N+1.
        if queryset is None:
            queryset = self.get_queryset()
        turmas_map = {
            t.id: (t.nome, t.ano_letivo)
            for t in Turma.objects.filter(
                id__in=queryset.values_list("turma_id", flat=True)
            )
        }

        idx_turma = dataset.headers.index("turma")
        dataset.headers[idx_turma] = "turma_nome"
        # Insere `ano_letivo` logo depois (mais legível pro humano).
        novos_dados = []
        for linha in dataset:
            valor = linha[idx_turma]
            try:
                turma_id = int(valor) if valor else None
            except (TypeError, ValueError):
                turma_id = None
            nome, ano = turmas_map.get(turma_id, ("", ""))
            nova_linha = list(linha)
            nova_linha[idx_turma] = nome
            nova_linha.insert(idx_turma + 1, ano)
            novos_dados.append(tuple(nova_linha))

        dataset.headers.insert(idx_turma + 1, "ano_letivo")
        # `tablib.Dataset` não tem replace_all, recriamos do zero.
        novo = type(dataset)(headers=dataset.headers)
        for linha in novos_dados:
            novo.append(linha)
        return novo

    def before_import_row(self, row, **kwargs):
        super().before_import_row(row, **kwargs)

        escola_id = self.contexto.escola_id if self.contexto else None
        if escola_id is None:
            raise ValueError(
                "Escola não definida no contexto do import."
            )

        # Aceita tanto `turma` (id ou nome) quanto `turma_nome` + `ano_letivo`.
        turma_nome = (
            row.get("turma_nome")
            or row.get("turma")
            or ""
        )
        turma_nome = str(turma_nome).strip()
        if not turma_nome:
            raise ValueError(
                "Coluna 'turma' (ou 'turma_nome') obrigatória no import de Aluno."
            )

        # Se o valor já é numérico, deixa o widget resolver direto.
        if turma_nome.isdigit():
            row["turma"] = int(turma_nome)
            return

        ano_extras = (self.contexto.extras or {}).get("ano_letivo_padrao")
        ano_linha = row.get("ano_letivo") or ano_extras
        if not ano_linha:
            raise ValueError(
                "Ano letivo obrigatório quando a turma é referenciada pelo nome. "
                "Preencha a coluna 'ano_letivo' ou o campo 'Ano letivo padrão' "
                "no formulário de import."
            )
        ano_letivo = int(ano_linha)

        turma = _turma_por_nome_ano(escola_id, turma_nome, ano_letivo)
        if turma is None:
            turno_padrao = (self.contexto.extras or {}).get("turno_padrao")
            if not turno_padrao:
                raise ValueError(
                    f"Turma '{turma_nome}' ({ano_letivo}) não existe e o "
                    "campo 'Turno padrão' não foi preenchido. Defina o turno "
                    "padrão no formulário de import pra criar a turma "
                    "automaticamente."
                )
            turno = _normalizar_turno(turno_padrao)
            turma = Turma.objects.create(
                escola_id=escola_id,
                nome=turma_nome,
                ano_letivo=ano_letivo,
                turno=turno,
                ativa=True,
            )
            logger.info(
                "Turma criada automaticamente no import de alunos: %s/%s",
                turma_nome,
                ano_letivo,
            )

        row["turma"] = turma.id

    def _descricao_linha(self, row) -> str:
        nome = row.get("nome_completo") or row.get("matricula") or "?"
        return str(nome)


# ===================================================================== #
# Professor                                                              #
# ===================================================================== #


class ProfessorResource(BaseEscolaResource):
    """Import/export de Professor.

    Cria `Usuario` (perfil=professor, senha unusable) + `Professor` numa
    transação e dispara email de redefinição de senha — fluxo idêntico
    ao `Esqueci minha senha`, então o professor recebe o link e define
    a senha dele mesmo.

    Chave natural: `(escola, usuario.username)` — duplicado é pulado.

    Campos da planilha:
        username, first_name, last_name, email, ativo (opcional)
    """

    # Campos "virtuais" que não existem em Professor mas vêm da planilha.
    # `attribute=None` impede que o ModelResource tente atribuir direto
    # ao Professor — usamos esses valores em `before_save_instance`.
    username = fields.Field(column_name="username", attribute=None)
    first_name = fields.Field(column_name="first_name", attribute=None)
    last_name = fields.Field(column_name="last_name", attribute=None)
    email = fields.Field(column_name="email", attribute=None)
    ativo = fields.Field(
        column_name="ativo",
        attribute="ativo",
        widget=BooleanWidget(),
        default=True,
    )

    class Meta:
        model = Professor
        # Chave natural é o username do usuário vinculado. O
        # `get_or_init_instance` do django-import-export usa esses campos
        # pra buscar a instância — implementamos `get_instance` manualmente
        # porque `username` é via FK, não atributo direto.
        import_id_fields = ("username",)
        # `username`/`first_name`/`last_name`/`email` são campos virtuais
        # (não existem em Professor, vêm da planilha pra criar Usuario
        # vinculado). Declarados aqui pra silenciar o warning do
        # django-import-export e ficarem visíveis no template/export.
        fields = ("username", "first_name", "last_name", "email", "ativo")
        export_order = ("username", "first_name", "last_name", "email", "ativo")

    def get_instance(self, instance_loader, row):
        """Resolve Professor existente pelo username do usuário vinculado.

        O loader padrão só sabe procurar por campos diretos do modelo —
        `username` é via OneToOne, então sobrescrevemos.
        """
        username = (row.get("username") or "").strip()
        if not username:
            return None
        escola_id = self.contexto.escola_id if self.contexto else None
        return (
            Professor.objects.filter(
                usuario__username=username, escola_id=escola_id
            )
            .select_related("usuario")
            .first()
        )

    def export_resource(self, obj, *args, **kwargs):
        """Hidrata os campos virtuais (do Usuario) no export."""
        linha = super().export_resource(obj, *args, **kwargs)
        # `linha` é uma lista alinhada com `get_export_headers`.
        headers = self.get_export_headers()
        usuario = obj.usuario
        mapeamento = {
            "username": usuario.username,
            "first_name": usuario.first_name,
            "last_name": usuario.last_name,
            "email": usuario.email,
        }
        for nome, valor in mapeamento.items():
            if nome in headers:
                linha[headers.index(nome)] = valor
        return linha

    def import_instance(self, instance, row, **kwargs):  # noqa: ARG002
        """Cria Usuario + Professor numa transação atômica.

        Sobrescreve o caminho normal porque o ModelResource padrão não
        sabe criar a OneToOne relacionada. Roda só quando a instância é
        nova (linhas duplicadas são puladas em `skip_row`).
        """
        escola_id = self.contexto.escola_id if self.contexto else None
        if escola_id is None:
            raise ValueError("Escola não definida no contexto do import.")

        username = (row.get("username") or "").strip()
        first_name = (row.get("first_name") or "").strip()
        last_name = (row.get("last_name") or "").strip()
        email = (row.get("email") or "").strip()

        if not username:
            raise ValueError("Coluna 'username' é obrigatória.")
        if not email:
            raise ValueError(
                f"Coluna 'email' é obrigatória (usuário {username}) — "
                "usamos pra enviar o link de definição de senha."
            )

        # Username globalmente único. Se já existe (em qualquer escola),
        # falha a linha com erro claro em vez de IntegrityError.
        if Usuario.objects.filter(username=username).exists():
            raise ValueError(
                f"Já existe usuário com username '{username}' no sistema. "
                "Use outro username ou deixe a linha de fora."
            )

        with transaction.atomic():
            usuario = Usuario.objects.create(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=email,
                perfil=Usuario.Perfil.PROFESSOR,
                escola_id=escola_id,
            )
            # Senha aleatória, não usada — o professor define a dele via
            # link de redefinição. `set_unusable_password` deixa o
            # password hash como `!` (não-validável), o que efetivamente
            # bloqueia login até o reset.
            usuario.set_password(secrets.token_urlsafe(32))
            usuario.save(update_fields=["password"])

            instance.usuario = usuario
            instance.escola_id = escola_id
            instance.ativo = row.get("ativo", True)
            return instance

    def after_save_instance(self, instance, row, **kwargs):  # noqa: ARG002
        """Dispara email de reset de senha pro professor recém-criado.

        Só roda no save real (não no dry-run) — o
        `django-import-export` gerencia o `using_transactions` via kwarg
        `dry_run` que checamos.
        """
        if kwargs.get("dry_run"):
            return
        try:
            _token_obj, token_cru = PasswordResetToken.gerar(instance.usuario)
            enviar_link_redefinicao(instance.usuario, token_cru)
        except Exception:  # noqa: BLE001 — log e segue (não falha o import)
            logger.exception(
                "Falha ao enviar email de definição de senha pro professor importado",
                extra={"usuario_id": instance.usuario_id},
            )

    def _descricao_linha(self, row) -> str:
        username = row.get("username", "?")
        nome = " ".join(
            v
            for v in [row.get("first_name"), row.get("last_name")]
            if v
        ).strip()
        return f"{nome or username} ({username})"


# ===================================================================== #
# Lecionamento                                                           #
# ===================================================================== #


class LecionamentoResource(BaseEscolaResource):
    """Import/export de Lecionamento (Professor × Turma × Disciplina).

    Colunas no CSV:
        professor_username, turma_nome, ano_letivo, disciplina_nome, ativo

    Chave natural: `(professor, turma, disciplina)` — duplicado pulado.

    Não cria entidades faltantes (professor, turma ou disciplina ausente
    → linha rejeitada com mensagem clara). A justificativa é segurança:
    criar professor via planilha exige email pra reset; criar turma
    exige turno. Esses dois imports são feitos antes (em arquivos
    separados) e Lecionamento só amarra o que já existe.
    """

    professor = fields.Field(
        column_name="professor",
        attribute="professor_id",
        widget=IntegerWidget(),
    )
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
    ativo = fields.Field(
        column_name="ativo",
        attribute="ativo",
        widget=BooleanWidget(),
        default=True,
    )

    class Meta:
        model = Lecionamento
        import_id_fields = ("professor", "turma", "disciplina")
        fields = ("escola", "professor", "turma", "disciplina", "ativo")
        export_order = ("professor", "turma", "disciplina", "ativo")

    def before_import(self, dataset, **kwargs):
        """Injeta colunas placeholders pros FK pra passar a validação de headers.

        A lib checa em `_check_import_id_fields` se as colunas estão no
        `dataset.headers`. Como o CSV traz `professor_username`,
        `turma_nome`, `disciplina_nome`, adicionamos placeholders nulos
        — o `before_import_row` resolve nomes → IDs e sobrescreve.
        """
        super().before_import(dataset, **kwargs)
        for nome in ("professor", "turma", "disciplina"):
            if nome not in dataset.headers:
                dataset.append_col(
                    [0] * dataset.height,
                    header=nome,
                )

    def export(self, queryset=None, **kwargs):
        """Substitui colunas numéricas (FK ids) pelos nomes legíveis."""
        dataset = super().export(queryset=queryset, **kwargs)
        if queryset is None:
            queryset = self.get_queryset()

        # Caches pra evitar N+1.
        professores = {
            p.id: p.usuario.username
            for p in Professor.objects.filter(
                id__in=queryset.values_list("professor_id", flat=True)
            ).select_related("usuario")
        }
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

        novos_headers = [
            "professor_username",
            "turma_nome",
            "ano_letivo",
            "disciplina_nome",
            "ativo",
        ]
        novo = type(dataset)(headers=novos_headers)
        headers_atuais = dataset.headers
        for linha in dataset:
            mapa = dict(zip(headers_atuais, linha))
            try:
                turma_id = int(mapa.get("turma") or 0)
            except (TypeError, ValueError):
                turma_id = 0
            try:
                prof_id = int(mapa.get("professor") or 0)
            except (TypeError, ValueError):
                prof_id = 0
            try:
                disc_id = int(mapa.get("disciplina") or 0)
            except (TypeError, ValueError):
                disc_id = 0
            nome_turma, ano = turmas.get(turma_id, ("", ""))
            novo.append(
                (
                    professores.get(prof_id, ""),
                    nome_turma,
                    ano,
                    disciplinas.get(disc_id, ""),
                    mapa.get("ativo", True),
                )
            )
        return novo

    def before_import_row(self, row, **kwargs):
        super().before_import_row(row, **kwargs)
        escola_id = self.contexto.escola_id if self.contexto else None
        if escola_id is None:
            raise ValueError("Escola não definida no contexto do import.")

        # Resolve professor.
        prof_username = (
            row.get("professor_username")
            or row.get("professor")
            or ""
        )
        prof_username = str(prof_username).strip()
        if prof_username.isdigit():
            row["professor"] = int(prof_username)
        else:
            if not prof_username:
                raise ValueError("Coluna 'professor_username' obrigatória.")
            prof = (
                Professor.objects.filter(
                    usuario__username=prof_username, escola_id=escola_id
                )
                .first()
            )
            if prof is None:
                raise ValueError(
                    f"Professor '{prof_username}' não encontrado nesta escola. "
                    "Cadastre o professor antes (import separado ou pela UI)."
                )
            row["professor"] = prof.id

        # Resolve turma.
        turma_nome = (
            row.get("turma_nome") or row.get("turma") or ""
        )
        turma_nome = str(turma_nome).strip()
        if turma_nome.isdigit():
            row["turma"] = int(turma_nome)
        else:
            if not turma_nome:
                raise ValueError("Coluna 'turma_nome' obrigatória.")
            ano = row.get("ano_letivo")
            if not ano:
                raise ValueError(
                    "Coluna 'ano_letivo' obrigatória pra resolver turma por nome."
                )
            turma = _turma_por_nome_ano(escola_id, turma_nome, int(ano))
            if turma is None:
                raise ValueError(
                    f"Turma '{turma_nome}' ({ano}) não existe. "
                    "Cadastre a turma antes."
                )
            row["turma"] = turma.id

        # Resolve disciplina.
        disc_nome = (
            row.get("disciplina_nome") or row.get("disciplina") or ""
        )
        disc_nome = str(disc_nome).strip()
        if disc_nome.isdigit():
            row["disciplina"] = int(disc_nome)
        else:
            if not disc_nome:
                raise ValueError("Coluna 'disciplina_nome' obrigatória.")
            disc = _disciplina_por_nome(escola_id, disc_nome)
            if disc is None:
                raise ValueError(
                    f"Disciplina '{disc_nome}' não existe. "
                    "Cadastre a disciplina antes."
                )
            row["disciplina"] = disc.id

    def _descricao_linha(self, row) -> str:
        prof = row.get("professor_username") or row.get("professor") or "?"
        turma = row.get("turma_nome") or row.get("turma") or "?"
        disc = row.get("disciplina_nome") or row.get("disciplina") or "?"
        return f"{prof} → {disc} em {turma}"
