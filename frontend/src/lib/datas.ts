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
