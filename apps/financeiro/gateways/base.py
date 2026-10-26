"""Contrato do gateway de cobrança — o que o financeiro pede, não o que
o provedor oferece.

O vocabulário aqui é o nosso (`Pagamento.Metodo`, `Decimal`, `date`), e é
de propósito: se o contrato falasse `billingType` e `dueDate`, trocar de
provedor pediria mudança em quem chama, e a interface não teria servido
pra nada. A tradução pro dialeto de cada um mora no módulo dele.

Três decisões que custaram discussão e estão registradas no
`FINANCEIRO.md` §6:

- **Pagador é criado antes da cobrança.** O Asaas (e os concorrentes)
  exige um cadastro de cliente pra pendurar a cobrança. Por isso são dois
  métodos, e o id do pagador é guardado pra reuso — não dá pra inferir do
  nosso banco qual pagador já existe lá.
- **A situação devolvida é a nossa, reduzida.** O Asaas tem catorze
  estados; a `Fatura` tem quatro. A redução é decisão de produto e mora
  no adaptador, mas o conjunto possível é fixado aqui pra que nenhum
  provedor invente um quinto estado que o `services.py` não saiba tratar.
- **`PAGA` é dinheiro liquidado, não promessa.** Um estado intermediário
  ("confirmado", "em análise") mapeia pra `PENDENTE`, nunca pra `PAGA`:
  conciliar cedo marcaria como paga uma fatura que ainda pode ser
  estornada. Ver `SituacaoCobranca`.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum


class ErroDeGateway(Exception):
    """Falha ao falar com o provedor.

    O `services.py` e a view tratam gateway como coisa que falha — rede
    cai, chave expira, provedor recusa. Erro de gateway nunca sobe como
    exceção crua: vira esta, com mensagem que a secretaria possa ler.

    `codigo` é o código do provedor quando existe (`invalid_access_token`,
    por exemplo), guardado pra diagnóstico no log e no Sentry. Fica vazio
    quando a falha é nossa ou de transporte.
    """

    def __init__(self, mensagem: str, codigo: str = "") -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.codigo = codigo


class ErroTemporario(ErroDeGateway):
    """Falha que pode dar certo se repetida: timeout, 5xx, rate limit.

    Separado do permanente porque só este justifica retentar. Quem chama
    decide se repete; a distinção existe pra que não precise adivinhar
    pelo texto da mensagem.
    """


class ErroPermanente(ErroDeGateway):
    """Falha que repetir não resolve: payload inválido, chave errada, 4xx.

    Repetir aqui queima cota e esconde o problema real — o CPF malformado
    continua malformado na segunda tentativa.
    """


class SituacaoCobranca(Enum):
    """Situação de uma cobrança, no vocabulário reduzido do financeiro.

    Os valores são **os mesmos** de `Fatura.Status`, de propósito: a
    conversão fica literal e ninguém precisa manter um mapa de quatro
    linhas que só existiria pra traduzir sinônimo. Um enum próprio, e não
    o do modelo, porque a camada de gateway não importa model — e porque
    é aqui que a regra da redução fica escrita. Um teste trava os dois
    conjuntos juntos.

    O adaptador de cada provedor é quem reduz o catálogo dele a isto, e a
    regra é conservadora: na dúvida, `PENDENTE`.

    `PAGO` significa dinheiro liquidado e não mais reversível pelo fluxo
    normal — é o único que autoriza `services.registrar_pagamento`. Um
    provedor que tenha estado intermediário de confirmação (o Asaas tem,
    e pode voltar atrás em até 72h) mapeia esse estado pra `PENDENTE`.
    """

    PENDENTE = "pendente"
    PAGO = "pago"
    VENCIDO = "vencido"
    CANCELADO = "cancelado"


@dataclass(frozen=True)
class DadosPagador:
    """Quem paga, no cadastro do provedor.

    `documento` é CPF ou CNPJ só com dígitos — o provedor é quem valida,
    e normalizar aqui evita que a máscara da tela vire erro remoto.

    `referencia_externa` leva o nosso id pra que o cadastro de lá possa
    ser reconciliado com o nosso sem depender de nome, que repete.
    """

    nome: str
    documento: str
    email: str = ""
    telefone: str = ""
    referencia_externa: str = ""


@dataclass(frozen=True)
class Pagador:
    """Pagador já cadastrado no provedor. `id_externo` é o que se guarda."""

    id_externo: str


@dataclass(frozen=True)
class DadosCobranca:
    """Uma cobrança a criar.

    `metodo` usa os valores de `Pagamento.Metodo` (`pix`, `boleto`,
    `cartao`) ou vazio pra deixar o pagador escolher na página do
    provedor — que é o default razoável pra mensalidade, já que a família
    decide na hora. `dinheiro` não aparece aqui de propósito: dinheiro na
    secretaria não passa por gateway nenhum.

    `referencia_externa` recebe o id da `Fatura`. É o que permite achar a
    fatura a partir de um evento do provedor sem confiar no corpo dele.

    `multa_percentual` e `juros_mes_percentual` são as cláusulas do
    `PlanoCobranca`, repassadas pro provedor calcular o encargo no
    documento que a família paga. Vão aqui — e não ficam só no nosso
    `Fatura.encargos()` — porque o encargo tem que estar **no boleto**:
    sem isso o atraso sai cobrado pelo valor de face, e a escola que
    contratou 2% de multa teria que cobrar a diferença à mão, que é
    exatamente o trabalho manual que este módulo existe pra tirar.
    Percentuais, não valores, porque é assim que a cláusula é escrita e é
    o que o provedor espera (o cálculo sobre os dias de atraso é dele).
    """

    pagador: Pagador
    valor: Decimal
    vencimento: date
    descricao: str = ""
    metodo: str = ""
    referencia_externa: str = ""
    multa_percentual: Decimal = Decimal("0.00")
    juros_mes_percentual: Decimal = Decimal("0.00")


@dataclass(frozen=True)
class Cobranca:
    """Cobrança como ela existe no provedor.

    `link_pagamento` é a página onde a família paga, servindo a qualquer
    método — não o PDF do boleto, que não ajuda quem escolheu Pix. É o
    que vai pro `Fatura.link_pagamento`.

    `valor_pago` vem `None` enquanto não há liquidação; zero seria
    ambíguo com estorno total.

    `metodo` é o meio pelo qual a cobrança foi paga, nos valores de
    `Pagamento.Metodo`, e vem vazio enquanto ninguém pagou. Existe porque
    a conciliação precisa gravar o meio no `Pagamento`, e quem sabe disso
    é o provedor: a cobrança criada como "pagador escolhe" só revela o
    meio quando a família escolhe.
    """

    id_externo: str
    situacao: SituacaoCobranca
    valor: Decimal
    vencimento: date
    link_pagamento: str = ""
    valor_pago: Decimal | None = None
    data_pagamento: date | None = None
    metodo: str = ""


class CobrancaGateway(ABC):
    """O que um provedor de cobrança precisa saber fazer.

    Quatro operações, que são as que o fluxo do `FINANCEIRO.md` §6 usa:
    cadastrar o pagador, criar a cobrança, reconsultar antes de conciliar
    e cancelar quando a fatura é cancelada aqui.

    Toda implementação levanta `ErroTemporario` ou `ErroPermanente` em
    falha — nunca a exceção da biblioteca HTTP, que vazaria o provedor
    pra quem chama.
    """

    @abstractmethod
    def criar_pagador(self, dados: DadosPagador) -> Pagador:
        """Cadastra o pagador e devolve o id de lá.

        Não é idempotente do lado do provedor (o Asaas aceita duplicata),
        então quem chama guarda o `id_externo` e não chama de novo.
        """

    @abstractmethod
    def criar_cobranca(self, dados: DadosCobranca) -> Cobranca:
        """Cria a cobrança e devolve id e link."""

    @abstractmethod
    def consultar_cobranca(self, id_externo: str) -> Cobranca:
        """Lê a cobrança no provedor.

        É a fonte da verdade na conciliação: o corpo do webhook não é
        confiável pra valor, então a fatia 5 reconsulta antes de escrever
        dinheiro (`FINANCEIRO.md` §6).
        """

    @abstractmethod
    def cancelar_cobranca(self, id_externo: str) -> Cobranca:
        """Cancela a cobrança no provedor.

        Chamado quando a fatura é cancelada aqui — sem isso a família
        continuaria recebendo lembrete de uma cobrança que a escola já
        baixou.
        """
