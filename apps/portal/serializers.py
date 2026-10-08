"""Serializers de leitura do portal do responsável.

Só leitura e com campos escolhidos a dedo: o que sai daqui chega a um
usuário externo. Nada de autoria de comunicado, log de entrega de outros
alunos, observação interna de professor ou qualquer dado agregado da turma
(`PORTAL.md`, seção 4.2).
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.avaliacao.models import PeriodoAvaliativo
from apps.comunicados.models import Comunicado
from apps.common.serializers import validate_escola_do_usuario
from apps.escola.models import Aluno
from apps.materiais.models import Material
from apps.ocorrencias.models import Ocorrencia

from .models import Responsavel, ResponsavelAluno


class FilhoSerializer(serializers.ModelSerializer):
    turma = serializers.CharField(source="turma.nome", read_only=True)
    ano_letivo = serializers.IntegerField(source="turma.ano_letivo", read_only=True)

    class Meta:
        model = Aluno
        fields = ["id", "nome_completo", "matricula", "turma", "ano_letivo", "ativo"]
        read_only_fields = fields


class PeriodoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PeriodoAvaliativo
        fields = ["id", "nome", "ano_letivo", "data_inicio", "data_fim"]
        read_only_fields = fields


class OcorrenciaPortalSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    # O email da ocorrência já mostra o professor ao responsável; aqui é o
    # mesmo dado, sem id interno.
    professor = serializers.SerializerMethodField()

    class Meta:
        model = Ocorrencia
        fields = [
            "id",
            "data_ocorrencia",
            "descricao",
            "status",
            "status_display",
            "professor",
        ]
        read_only_fields = fields

    def get_professor(self, obj) -> str | None:
        if obj.professor and obj.professor.usuario:
            return obj.professor.usuario.get_full_name() or None
        return None


class MaterialPortalSerializer(serializers.ModelSerializer):
    disciplina = serializers.CharField(source="disciplina.nome", read_only=True)
    professor = serializers.CharField(
        source="professor.usuario.get_full_name", read_only=True
    )

    class Meta:
        model = Material
        fields = ["id", "titulo", "descricao", "link", "disciplina", "professor", "publicado_em"]
        read_only_fields = fields


class ComunicadoPortalSerializer(serializers.ModelSerializer):
    # Quais filhos *deste* responsável o comunicado alcançou. Preenchido
    # pela view (`_alunos_por_comunicado`), sem tocar no log dos outros.
    alunos = serializers.SerializerMethodField()

    class Meta:
        model = Comunicado
        fields = ["id", "titulo", "mensagem", "enviado_em", "alunos"]
        read_only_fields = fields

    def get_alunos(self, obj) -> list[dict]:
        return self.context["alunos_por_comunicado"].get(obj.pk, [])


class ResponsavelAlunoResumoSerializer(serializers.ModelSerializer):
    """Aluno vinculado, como a tela de responsáveis do staff precisa ver."""

    turma = serializers.CharField(source="turma.nome", read_only=True)

    class Meta:
        model = Aluno
        fields = ["id", "nome_completo", "turma", "ativo"]
        read_only_fields = fields


class ResponsavelStaffSerializer(serializers.ModelSerializer):
    """Responsável visto pela secretaria (fatia 6b). Somente leitura.

    Diferente dos outros serializers deste módulo, este NÃO é consumido
    pelo portal: é a tela de gestão do staff. Mesmo assim nada de senha
    sai daqui — `situacao` já diz o que a escola precisa saber sobre o
    acesso, sem expor hash nem token.
    """

    alunos = ResponsavelAlunoResumoSerializer(many=True, read_only=True)
    situacao = serializers.SerializerMethodField()
    situacao_display = serializers.SerializerMethodField()
    # Vem da annotation do viewset (Subquery), não de query por linha.
    convite_expira_em = serializers.DateTimeField(read_only=True, default=None)
    ultimo_acesso = serializers.DateTimeField(
        source="last_login", read_only=True
    )

    class Meta:
        model = Responsavel
        fields = [
            "id",
            "nome",
            "email",
            "ativo",
            "situacao",
            "situacao_display",
            "convite_expira_em",
            "ultimo_acesso",
            "alunos",
            "criado_em",
        ]
        read_only_fields = fields

    # `PORTAL.md` lista três situações (sem convite / convidado / ativo).
    # Duas foram acrescentadas porque mostrar o contrário seria mentira:
    # `convite_expirado` (o convite tem 7 dias e o pai não usou — exibir
    # "convidado" faria a secretaria esperar por nada) e `inativo` (a conta
    # foi desativada, então convidar não é o próximo passo).
    SITUACOES = {
        "inativo": "Inativo",
        "ativo": "Acesso ativo",
        "convidado": "Convite enviado",
        "convite_expirado": "Convite expirado",
        "sem_convite": "Sem convite",
    }

    def get_situacao(self, obj) -> str:
        if not obj.ativo:
            return "inativo"
        # `has_usable_password` lê o campo já carregado: sem query extra.
        if obj.has_usable_password():
            return "ativo"
        if getattr(obj, "tem_convite_pendente", False):
            return "convidado"
        if getattr(obj, "tem_convite", False):
            return "convite_expirado"
        return "sem_convite"

    def get_situacao_display(self, obj) -> str:
        return self.SITUACOES[self.get_situacao(obj)]


class ResponsavelAlunoStaffSerializer(serializers.ModelSerializer):
    """Vínculo responsável × aluno, escrito pela secretaria (fatia 4).

    Este é o serializer mais sensível do projeto. `ResponsavelAluno` é o
    modelo que decide quem lê o boletim, as ocorrências e os comunicados
    de qual aluno (`PORTAL.md`, seção 4.2) — um vínculo indevido é acesso
    indevido aos dados de uma criança, não um registro errado.

    Por isso o guard é em **duas camadas, com propósitos diferentes**:

    1. `validate_responsavel`/`validate_aluno` checam cada lado contra a
       escola de quem está logado. É o guard de IDOR do projeto
       (`validate_escola_do_usuario`), e sem ele um diretor da Escola X
       escreveria na Escola Y mandando os ids no body.
    2. `validate()` delega ao `clean()` do model, que exige os dois lados
       na **mesma** escola.

    As duas são necessárias e nenhuma substitui a outra: a (1) sozinha
    deixaria passar responsável de X com aluno de Y (ambos legítimos para
    um admin global); a (2) sozinha deixaria passar um par
    inteiramente de outra escola, porque responsável e aluno concordam
    entre si. É esse segundo caso que tem teste próprio — ele passa por
    `clean()` sem reclamar.
    """

    responsavel_nome = serializers.CharField(
        source="responsavel.nome", read_only=True
    )
    responsavel_email = serializers.CharField(
        source="responsavel.email", read_only=True
    )
    aluno_nome = serializers.CharField(
        source="aluno.nome_completo", read_only=True
    )
    aluno_turma = serializers.CharField(source="aluno.turma.nome", read_only=True)
    aluno_ativo = serializers.BooleanField(source="aluno.ativo", read_only=True)

    class Meta:
        model = ResponsavelAluno
        fields = [
            "id",
            "responsavel",
            "responsavel_nome",
            "responsavel_email",
            "aluno",
            "aluno_nome",
            "aluno_turma",
            "aluno_ativo",
            "criado_em",
        ]
        read_only_fields = [
            "id",
            "responsavel_nome",
            "responsavel_email",
            "aluno_nome",
            "aluno_turma",
            "aluno_ativo",
            "criado_em",
        ]

    def validate_responsavel(self, value):
        validate_escola_do_usuario(
            value.escola,
            self.context.get("request"),
            "Você só pode vincular responsável da sua própria escola.",
        )
        return value

    def validate_aluno(self, value):
        validate_escola_do_usuario(
            value.escola,
            self.context.get("request"),
            "Você só pode vincular aluno da sua própria escola.",
        )
        return value

    def validate(self, attrs: dict) -> dict:
        """Roda o `clean()` do model — a regra de mesma escola mora lá.

        Replicar a comparação aqui criaria uma segunda cópia da regra que
        decide acesso a dado de aluno, e duas cópias divergem.
        """
        instance = ResponsavelAluno(
            responsavel=attrs.get("responsavel"), aluno=attrs.get("aluno")
        )
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        return attrs
