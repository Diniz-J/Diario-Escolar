"""Serializers da app comunicados."""
from rest_framework import serializers

from apps.common.serializers import (
    AutoEscopoEscolaSerializerMixin,
    validate_escola_do_usuario,
)

from .models import Comunicado, ComunicadoDestinatario


class ComunicadoDestinatarioSerializer(serializers.ModelSerializer):
    """Log de entrega — somente leitura.

    As linhas são criadas pelo serviço de disparo, nunca pela API: expor
    escrita aqui permitiria "consertar" um log de auditoria.
    """

    aluno_nome = serializers.CharField(
        source="aluno.nome_completo", read_only=True
    )
    turma_nome = serializers.CharField(source="aluno.turma.nome", read_only=True)
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )

    class Meta:
        model = ComunicadoDestinatario
        fields = [
            "id",
            "comunicado",
            "aluno",
            "aluno_nome",
            "turma_nome",
            "email",
            "nome_responsavel",
            "status",
            "status_display",
            "erro",
            "enviado_em",
        ]
        read_only_fields = fields


class ComunicadoSerializer(
    AutoEscopoEscolaSerializerMixin, serializers.ModelSerializer
):
    """CRUD do comunicado.

    Tudo que descreve o **resultado** do disparo (status, contadores,
    datas, quem enviou) é read-only: quem muda isso é o serviço de envio.
    O cliente só controla conteúdo (`titulo`, `mensagem`) e público
    (`destino`, `turmas`).
    """

    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    destino_display = serializers.CharField(
        source="get_destino_display", read_only=True
    )
    criado_por_nome = serializers.SerializerMethodField()
    enviado_por_nome = serializers.SerializerMethodField()
    editavel = serializers.BooleanField(read_only=True)

    class Meta:
        model = Comunicado
        fields = [
            "id",
            "escola",
            "titulo",
            "mensagem",
            "destino",
            "destino_display",
            "turmas",
            "status",
            "status_display",
            "editavel",
            "enviado_em",
            "criado_por",
            "criado_por_nome",
            "enviado_por",
            "enviado_por_nome",
            "total_destinatarios",
            "total_enviados",
            "total_falhas",
            "total_sem_email",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = [
            "id",
            "status",
            "enviado_em",
            "criado_por",
            "enviado_por",
            "total_destinatarios",
            "total_enviados",
            "total_falhas",
            "total_sem_email",
            "criado_em",
            "atualizado_em",
        ]
        # `escola` opcional — `AutoEscopoEscolaSerializerMixin` preenche a
        # partir do usuário autenticado.
        extra_kwargs = {"escola": {"required": False}}

    def _nome(self, usuario) -> str | None:
        if usuario is None:
            return None
        return usuario.get_full_name() or usuario.username

    def get_criado_por_nome(self, obj) -> str | None:
        return self._nome(obj.criado_por)

    def get_enviado_por_nome(self, obj) -> str | None:
        return self._nome(obj.enviado_por)

    def validate_escola(self, value):
        return validate_escola_do_usuario(
            value,
            self.context.get("request"),
            "Você só pode criar comunicados na sua própria escola.",
        )

    def validate_titulo(self, value: str) -> str:
        titulo = (value or "").strip()
        if not titulo:
            raise serializers.ValidationError("Informe um título.")
        return titulo

    def validate_mensagem(self, value: str) -> str:
        mensagem = (value or "").strip()
        if not mensagem:
            raise serializers.ValidationError("Informe a mensagem do comunicado.")
        return mensagem

    def validate(self, attrs: dict) -> dict:
        """Valida público e imutabilidade pós-envio.

        Regras:
        - Comunicado já disparado não é editável (ver `Comunicado.editavel`).
          A checagem fica aqui e não só na view pra que qualquer caminho de
          escrita (incluindo PATCH parcial) seja barrado.
        - `destino="turmas"` exige ao menos uma turma, e todas da escola do
          comunicado — sem isso um diretor poderia endereçar a turma de
          outra escola e vazar o aviso.
        - `destino="escola"` ignora `turmas`: o público é resolvido no
          disparo. Guardar turmas aqui criaria um estado contraditório
          ("toda a escola, mas só o 1º A").
        """
        if self.instance is not None and not self.instance.editavel:
            raise serializers.ValidationError(
                {
                    "detail": (
                        "Este comunicado já foi disparado e não pode mais "
                        "ser alterado."
                    )
                }
            )

        escola = attrs.get("escola") or getattr(self.instance, "escola", None)
        destino = attrs.get("destino") or getattr(
            self.instance, "destino", Comunicado.Destino.ESCOLA
        )

        # `turmas` só é checada quando veio no payload; em PATCH que não a
        # menciona, vale o que já está salvo.
        turmas_no_payload = "turmas" in attrs
        turmas = attrs.get("turmas")
        if not turmas_no_payload and self.instance is not None:
            turmas = list(self.instance.turmas.all())

        if destino == Comunicado.Destino.TURMAS:
            if not turmas:
                raise serializers.ValidationError(
                    {
                        "turmas": (
                            "Selecione ao menos uma turma para este destino."
                        )
                    }
                )
            if escola and any(t.escola_id != escola.id for t in turmas):
                raise serializers.ValidationError(
                    {
                        "turmas": (
                            "As turmas devem pertencer à mesma escola do "
                            "comunicado."
                        )
                    }
                )
        elif turmas_no_payload:
            # Normaliza em vez de recusar: a UI troca o destino pra
            # "toda a escola" e não precisa limpar o campo manualmente.
            attrs["turmas"] = []

        return attrs
