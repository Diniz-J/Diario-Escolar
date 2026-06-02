"""Helpers de serializer compartilhados entre apps.

Concentra padrões que se repetem em muitos serializers:
- `AutoEscopoEscolaSerializerMixin`: auto-injeta `escola` no payload
  de criação a partir do `request.user.escola`. Esconde multi-tenant
  da UI — diretor/professor/secretaria não precisa selecionar escola.
- `validate_escola_do_usuario`: guard de IDOR (admin pode tudo;
  não-admin só pode escrever na própria escola mesmo passando outra
  no payload).
"""
from rest_framework import serializers


class AutoEscopoEscolaSerializerMixin:
    """Injeta `escola` no payload de criação quando ausente.

    Funciona em conjunto com a Meta `extra_kwargs = {"escola": {"required": False}}`
    do serializer. Executado em `to_internal_value` (antes da validação
    de campo e dos validators tipo UniqueTogether), então o resto do
    serializer enxerga o campo como se viesse no payload — inclusive o
    `UniqueTogetherValidator` que exige todos os campos do constraint.

    Quando o usuário tem `escola_id` no JWT, injeta. Quando não tem
    (admin/superuser global), nada acontece — o serializer falhará com
    "Este campo é obrigatório" pro admin global esquecer de mandar
    escola. Pode chamar `validate` no serializer pra customizar a
    mensagem se quiser.

    Em PATCH/PUT (com `self.instance` setado), também injeta — útil
    quando o admin quer atualizar sem mexer na escola (ainda assim,
    o `validate_escola` guard IDOR faz o trabalho de bloquear
    cross-tenant).
    """

    def to_internal_value(self, data):
        if "escola" not in data:
            request = self.context.get("request")
            if request is not None and request.user.is_authenticated:
                escola_id = getattr(request.user, "escola_id", None)
                if escola_id is not None:
                    # `data` pode ser dict (JSON request) ou QueryDict
                    # (form-encoded). QueryDict tem `_mutable`; dict
                    # comum não.
                    if hasattr(data, "_mutable"):
                        was_mutable = data._mutable
                        data._mutable = True
                        data["escola"] = escola_id
                        data._mutable = was_mutable
                    else:
                        # Cria uma cópia pra não mutar o request.data
                        # original do caller (boa prática).
                        data = {**data, "escola": escola_id}
        return super().to_internal_value(data)


def validate_escola_do_usuario(value, request, mensagem: str):
    """Guard IDOR pra `escola` em payloads de criação/edição.

    O `EscopoEscolaMixin` esconde leitura cross-escola, mas não bloqueia
    escrita — sem este guard, um diretor da Escola A poderia escrever na
    Escola B mandando `escola=B_id` no body. Admin e superuser passam
    livremente por design (operam em todas as escolas).

    Uso típico:

        def validate_escola(self, value):
            return validate_escola_do_usuario(
                value,
                self.context.get("request"),
                "Você só pode criar X na sua própria escola.",
            )

    `value` aqui é a instância de `Escola` já resolvida pelo DRF (não o
    id cru). Retorna o próprio `value` quando passa; levanta
    `ValidationError(mensagem)` quando falha.
    """
    if request is None or not request.user.is_authenticated:
        return value
    user = request.user
    if user.is_superuser or getattr(user, "perfil", None) == "admin":
        return value
    user_escola_id = getattr(user, "escola_id", None)
    if user_escola_id and value.id != user_escola_id:
        raise serializers.ValidationError(mensagem)
    return value
