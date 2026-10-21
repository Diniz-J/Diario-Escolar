// Datas no front. A conversão pra UTC é a origem de dois bugs que o
// projeto já pagou, então ela mora aqui e não espalhada pelas telas.
//
// `new Date().toISOString().slice(0, 10)` parece o jeito óbvio de pegar
// "hoje", mas `toISOString` converte pra UTC: em fuso negativo, das 21h
// (UTC-3) em diante o resultado é a data de AMANHÃ. Como o backend
// recusa data futura em ocorrência e em chamada
// (`apps/ocorrencias/serializers.py`, `apps/presenca/serializers.py`),
// o turno noturno recebia um formulário pré-preenchido que o servidor
// rejeitava — e o `max` do input, calculado do mesmo jeito, também vinha
// errado, então o browser nem barrava antes de enviar.
//
// Montar campo a campo a partir dos getters locais não passa por essa
// conversão: `getFullYear`/`getMonth`/`getDate` já respondem no fuso do
// usuário.
export function hojeISO(): string {
  const agora = new Date();
  const ano = agora.getFullYear();
  const mes = String(agora.getMonth() + 1).padStart(2, "0");
  const dia = String(agora.getDate()).padStart(2, "0");
  return `${ano}-${mes}-${dia}`;
}

// Formatação por **tipo de campo do backend**, e os nomes dizem qual é
// porque errar o par é o bug clássico aqui: aplicar o formatador de data
// pura num `DateTimeField` concatena `T00:00:00` numa string que já tem
// hora e offset, e o resultado é um `Invalid Date` na tela.

/**
 * Campo de data pura (`DateField`): `"2026-03-10"` -> `"10/03/2026"`.
 *
 * Faz split da string em vez de passar por `new Date`, porque
 * `new Date("2026-03-10")` é lido como UTC e, em fuso negativo, volta como
 * dia 9.
 */
export function formatarDataPura(iso: string): string {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

/**
 * Campo de data-hora (`DateTimeField`): data e hora locais, com `"—"` pra
 * nulo. Aqui `new Date` é o certo — a string do DRF traz offset, então a
 * conversão pro fuso do usuário é justamente o que se quer.
 */
export function formatarDataHora(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Campo de data-hora exibido só como dia: `"2026-03-10T21:30:00-03:00"` ->
 * `"10/03/2026"`. Existe porque o mural mostra "publicado em" sem hora, e
 * o campo é `DateTimeField`.
 */
export function formatarDiaDaDataHora(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR");
}
