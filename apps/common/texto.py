"""Normalizações de texto compartilhadas entre apps."""


def normalizar_email(valor: str | None) -> str:
    """Normaliza um email para comparação, deduplicação e armazenamento.

    Lowercase + strip. Existe porque duas features dependem de tratar
    `Maria@Example.com ` e `maria@example.com` como o mesmo endereço, e por
    motivos diferentes:

    - `comunicados`: sem isso, o responsável com dois filhos receberia o
      mesmo comunicado duas vezes (a deduplicação do lote é por endereço).
    - `portal`: sem isso, o unique por `(escola, email)` do `Responsavel`
      seria furado e o mesmo pai teria duas contas e dois convites.

    Ficou aqui, e não copiado nas duas, porque é regra de identidade: duas
    cópias divergem com o tempo e o efeito seria conta ou email duplicado
    pro mesmo responsável.
    """
    return (valor or "").strip().lower()
