"""Serializers do financeiro.

Duas coisas valem explicação, porque divergem do que as outras apps fazem:

1. **As invariantes não são espelhadas à mão aqui.** `materiais` e `aulas`
   reescrevem o `clean()` do modelo dentro do `validate()` do serializer
   (o DRF não chama `clean()`). Funciona quando a invariante é uma linha,
   mas o `PlanoCobranca` tem cinco — incluindo a sobreposição de vigência,
   que faz consulta ao banco. Duas cópias disso divergiriam, e divergência
   num módulo de dinheiro significa cobrança errada. Então o serializer
   roda o próprio `clean()` do modelo sobre uma cópia carregada com o
   payload (`_validar_pelo_clean`), e o modelo segue sendo a única fonte
   da verdade das regras.
2. **Quase tudo que mexe em dinheiro é read-only.** `status`, `valor_pago`
   e `data_pagamento` da fatura são escritos pelo `services.py` (fatia 3);
   `id_externo` e `link_pagamento`, pelo gateway (fatia 4). Deixar
   `status` editável pela API abriria o caminho de marcar "pago" sem
   pagamento nenhum, e `id_externo` digitado à mão é como se concilia a
   cobrança do aluno errado.
"""
import copy

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.common.serializers import (
    AutoEscopoEscolaSerializerMixin,
    validate_escola_do_usuario,
)

from .models import Fatura, FaturaItem, Pagamento, PlanoCobranca, validar_link


def erro_drf(exc: DjangoValidationError) -> serializers.ValidationError:
    """Converte o `ValidationError` do Django no do DRF.

    Preserva as chaves por campo, pra que o erro saia no campo certo do
    formulário em vez de virar um `detail` genérico. Público porque a view
    também precisa: o `services.py` valida com `full_clean()` (pra que a
    regra valha pros três chamadores — API, command e webhook), e sem
    esta tradução no limite da API a exceção do Django sobe como 500.
    """
    if hasattr(exc, "error_dict"):
        return serializers.ValidationError(exc.message_dict)
    return serializers.ValidationError({"detail": exc.messages})


def _validar_pelo_clean(serializer, attrs: dict) -> dict:
    """Roda o `clean()` do modelo sobre uma cópia carregada com o payload.

    Cópia rasa (`copy.copy`) pra não sujar a instância que o DRF vai
    salvar depois, preservando `pk` — de que o `plano_sobreposto()`
    precisa pra não colidir consigo mesmo num PATCH.

    Em `PATCH` parcial, a cópia parte da instância do banco, então as
    invariantes enxergam o registro completo (campo não enviado mantém o
    valor atual) em vez de só o pedaço que veio no corpo.

    Converte o `ValidationError` do Django no do DRF mantendo as chaves
    por campo, pra que o erro saia no campo certo do formulário.
    """
    if serializer.instance is not None:
        obj = copy.copy(serializer.instance)
    else:
        obj = serializer.Meta.model()
    for campo, valor in attrs.items():
        setattr(obj, campo, valor)
    # Admin global que não manda `escola` (e o mixin não deduz, porque o
    # JWT não tem `escola_id`) chegaria ao INSERT com `escola_id=None` numa
    # coluna NOT NULL e estouraria IntegrityError (500). Devolve 400
    # explícito — cobre os três serializers deste módulo de uma vez.
    if getattr(obj, "escola_id", None) is None:
        raise serializers.ValidationError({"escola": "Informe a escola."})
    try:
        obj.clean()
    except DjangoValidationError as exc:
        raise erro_drf(exc) from exc
    return attrs


class PlanoCobrancaSerializer(
    AutoEscopoEscolaSerializerMixin, serializers.ModelSerializer
):
    """Contrato financeiro do aluno."""

    aluno_nome = serializers.CharField(
        source="aluno.nome_completo", read_only=True
    )
    # Derivado: mensalidade já com o desconto aplicado. `DecimalField` (e
    # não `SerializerMethodField`) pra sair com as mesmas duas casas em
    # string dos outros campos de dinheiro — um método devolvendo
    # `Decimal` viraria float no JSON e o front teria dois formatos.
    valor_efetivo = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )

    class Meta:
        model = PlanoCobranca
        fields = [
            "id",
            "escola",
            "aluno",
            "aluno_nome",
            "valor_mensalidade",
            "dia_vencimento",
            "desconto_tipo",
            "desconto_valor",
            "valor_efetivo",
            "multa_percentual",
            "juros_mes_percentual",
            "vigencia_inicio",
            "vigencia_fim",
            "ativo",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]
        extra_kwargs = {"escola": {"required": False}}

    def validate_escola(self, value):
        return validate_escola_do_usuario(
            value,
            self.context.get("request"),
            "Você só pode criar plano de cobrança na sua própria escola.",
        )

    def validate(self, attrs: dict) -> dict:
        return _validar_pelo_clean(self, attrs)


class FaturaSerializer(AutoEscopoEscolaSerializerMixin, serializers.ModelSerializer):
    """Uma competência do contrato — a linha do contas a receber.

    `aluno` é read-only e deduzido do `plano`: o campo existe pra
    sustentar o unique de `(aluno, competencia)` (ver `FINANCEIRO.md`
    §3.1), não pra ser preenchido por quem chama. Deixá-lo aberto só
    criaria a chance de apontar pro aluno errado.
    """

    aluno_nome = serializers.CharField(
        source="aluno.nome_completo", read_only=True
    )
    saldo = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    encargos = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    valor_atualizado = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    dias_atraso = serializers.IntegerField(read_only=True)
    esta_vencida = serializers.BooleanField(read_only=True)
    # Declarado à mão: ao montar o `URLField` a partir do modelo, o DRF
    # descarta os validators do model field, e o `validar_link`
    # (só http/https) sumiria. Mesma armadilha documentada em
    # `apps/materiais/serializers.py`. Read-only aqui, mas o campo é
    # escrito pelo gateway na fatia 4 e o validator precisa valer lá.
    link_pagamento = serializers.URLField(
        max_length=500, read_only=True, validators=[validar_link]
    )

    class Meta:
        model = Fatura
        fields = [
            "id",
            "escola",
            "plano",
            "aluno",
            "aluno_nome",
            "competencia",
            "valor",
            "vencimento",
            "status",
            "valor_pago",
            "data_pagamento",
            "saldo",
            "encargos",
            "valor_atualizado",
            "dias_atraso",
            "esta_vencida",
            "id_externo",
            "link_pagamento",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = [
            "id",
            # Deduzido do plano (ver docstring).
            "aluno",
            # Escritos pelo services.py na conciliação (fatia 3).
            "status",
            "valor_pago",
            "data_pagamento",
            # Escritos pelo gateway (fatia 4).
            "id_externo",
            "criado_em",
            "atualizado_em",
        ]
        extra_kwargs = {"escola": {"required": False}}

    def validate_escola(self, value):
        return validate_escola_do_usuario(
            value,
            self.context.get("request"),
            "Você só pode criar fatura na sua própria escola.",
        )

    def validate(self, attrs: dict) -> dict:
        plano = attrs.get("plano") or getattr(self.instance, "plano", None)
        if plano is not None:
            # O aluno vem do contrato, nunca do corpo da requisição.
            attrs["aluno"] = plano.aluno

        self._recusar_competencia_repetida(attrs, plano)
        return _validar_pelo_clean(self, attrs)

    def _recusar_competencia_repetida(self, attrs: dict, plano) -> None:
        """Devolve 400 no lugar do 500 que o unique de banco daria.

        O `UniqueTogetherValidator` do DRF não cobre este caso: ele só
        monta a checagem quando todos os campos do constraint são
        graváveis, e `aluno` é read-only aqui de propósito. Sem esta
        validação, cobrar o mesmo aluno duas vezes no mês estouraria
        `IntegrityError` e o front mostraria erro de servidor em vez de
        dizer o que aconteceu.
        """
        aluno = attrs.get("aluno")
        competencia = attrs.get("competencia") or getattr(
            self.instance, "competencia", None
        )
        if not (aluno and competencia):
            return
        qs = Fatura.objects.filter(aluno=aluno, competencia=competencia)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {
                    "competencia": (
                        f"{aluno.nome_completo} já tem fatura na competência "
                        f"{competencia:%m/%Y}. Cada aluno tem uma mensalidade "
                        "por mês — edite a fatura existente em vez de criar "
                        "outra."
                    )
                }
            )


class FaturaItemSerializer(
    AutoEscopoEscolaSerializerMixin, serializers.ModelSerializer
):
    """Linha do detalhamento da fatura.

    `Fatura.valor` continua sendo o quanto cobrar; o item explica a
    composição (`FINANCEIRO.md` §3.5). O serializer não força a soma das
    linhas a bater com o total, pelo mesmo motivo que o modelo não força.
    """

    class Meta:
        model = FaturaItem
        fields = [
            "id",
            "escola",
            "fatura",
            "descricao",
            "valor",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]
        extra_kwargs = {"escola": {"required": False}}

    def validate_escola(self, value):
        return validate_escola_do_usuario(
            value,
            self.context.get("request"),
            "Você só pode criar item de fatura na sua própria escola.",
        )

    def validate(self, attrs: dict) -> dict:
        return _validar_pelo_clean(self, attrs)


class PagamentoSerializer(serializers.ModelSerializer):
    """Pagamento conciliado — representação de leitura.

    Sem `AutoEscopoEscolaSerializerMixin` nem `validate_escola`: este
    serializer não escreve. Quem escreve é `PagamentoCreateSerializer`,
    e mesmo ele não chama `save()` — delega em
    `services.registrar_pagamento()`.
    """

    aluno_nome = serializers.CharField(
        source="fatura.aluno.nome_completo", read_only=True
    )
    competencia = serializers.DateField(
        source="fatura.competencia", read_only=True
    )

    class Meta:
        model = Pagamento
        fields = [
            "id",
            "escola",
            "fatura",
            "aluno_nome",
            "competencia",
            "valor",
            "data",
            "metodo",
            "referencia_externa",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = fields


class PagamentoCreateSerializer(serializers.ModelSerializer):
    """Entrada do registro manual de pagamento (secretaria recebeu).

    Valida o payload e **não persiste**: a view entrega os dados a
    `services.registrar_pagamento()`, que cria o pagamento e reconcilia a
    fatura na mesma transação. Chamar `save()` aqui gravaria o pagamento
    com a fatura intocada — o estado que `FINANCEIRO.md` §2.4 existe pra
    impedir.

    `escola` não é campo de entrada: sai da fatura, dentro do service.
    O que precisa de guard é a fatura em si, senão um diretor registraria
    pagamento numa fatura de outra escola (o escopo do queryset esconde
    leitura, não bloqueia escrita).
    """

    # `validators=[]` desliga de propósito o `UniqueValidator` que o DRF
    # monta sozinho a partir do `UniqueConstraint` do modelo. Com ele, o
    # reenvio do mesmo pagamento (duplo clique no formulário, retry de
    # rede) morreria em 400 antes de chegar ao service — e é justamente o
    # service que sabe a resposta certa pra isso: devolver o pagamento
    # que já existe. O constraint continua no banco como rede.
    referencia_externa = serializers.CharField(
        max_length=64, required=False, allow_blank=True, validators=[]
    )

    class Meta:
        model = Pagamento
        fields = ["id", "fatura", "valor", "data", "metodo", "referencia_externa"]
        read_only_fields = ["id"]

    def validate_fatura(self, value):
        validate_escola_do_usuario(
            value.escola,
            self.context.get("request"),
            "Você só pode registrar pagamento de fatura da sua própria escola.",
        )
        return value
