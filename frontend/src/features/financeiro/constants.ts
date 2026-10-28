import type {
  DescontoTipo,
  Fatura,
  FaturaStatus,
  PagamentoMetodo,
} from "@/types/api";

// Badges de status seguindo o molde de ocorrência (DESIGN.md §6.1), não os
// pastels de presença (§6.2): status de fatura é estado de documento, do
// mesmo tipo que `aberta`/`resolvida`, e aquela paleta é deliberadamente
// específica da grade de chamada.
//
// Tokens onde existem (destructive, olive, muted) em vez de hex cru — a
// §8.3 trata override inline de paleta como anti-pattern. A exceção é a
// mostarda, que não tem token: é o hex da "família mostarda" da §6.3,
// pattern pra status em curso sem urgência.
//
//   pendente  → mostarda    "em aberto, dentro do prazo"
//   pago      → olive       "resolvido"
//   vencido   → destructive "atenção, passou do prazo"
//   cancelado → muted       "fora de jogo"
export const STATUS_FATURA: Record<
  FaturaStatus,
  { label: string; className: string }
> = {
  pendente: {
    label: "Pendente",
    className: "bg-mostarda text-ambar",
  },
  pago: {
    label: "Pago",
    className: "bg-olive/10 text-olive",
  },
  vencido: {
    label: "Vencido",
    className: "bg-destructive/15 text-destructive",
  },
  cancelado: {
    label: "Cancelado",
    className: "bg-muted text-muted-foreground",
  },
};

export const METODOS_PAGAMENTO: { value: PagamentoMetodo; label: string }[] = [
  { value: "pix", label: "Pix" },
  { value: "boleto", label: "Boleto" },
  { value: "cartao", label: "Cartão" },
  { value: "dinheiro", label: "Dinheiro" },
];

export const METODO_LABEL: Record<PagamentoMetodo, string> = Object.fromEntries(
  METODOS_PAGAMENTO.map((m) => [m.value, m.label]),
) as Record<PagamentoMetodo, string>;

export const DESCONTO_TIPOS: { value: DescontoTipo; label: string }[] = [
  { value: "nenhum", label: "Sem desconto" },
  { value: "percentual", label: "Percentual" },
  { value: "fixo", label: "Valor fixo" },
];

// Dinheiro chega do backend como string ("1000.00") pra não perder
// precisão. Converter aqui só pra exibir — nunca pra calcular: os
// derivados (saldo, encargos, valor atualizado) vêm prontos do backend.
export function formatarBRL(valor: string): string {
  return Number(valor).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

export function formatarCompetencia(iso: string): string {
  const [ano, mes] = iso.split("-");
  return `${mes}/${ano}`;
}

// Valor do input `type="month"` ("2026-03") pro formato que a API espera
// na competência, que é sempre o dia 1 do mês.
export function competenciaDoMes(mes: string): string {
  return `${mes}-01`;
}

// Quem pode ir pro gateway. Fica aqui, e não repetido na página e no
// dialog de detalhe, porque duas cópias divergiriam no dia em que o
// backend mudar a regra — e aí um dos dois ofereceria um botão que só
// devolve erro.
//
// O backend é a autoridade (recusa paga e cancelada, e é idempotente em
// quem já tem `id_externo`); isto é só pra não mostrar uma ação que já se
// sabe que não cabe. Fatura já emitida sai da lista porque o que ela
// precisa é do link, não de uma segunda cobrança.
export function podeEmitirCobranca(fatura: Fatura): boolean {
  return (
    !fatura.id_externo &&
    (fatura.status === "pendente" || fatura.status === "vencido")
  );
}
