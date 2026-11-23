import type { RegistroPresenca, TempoDetalhe } from "@/types/api";

import { horaCurta } from "@/features/grade/constants";

/**
 * Descreve o bloco de tempos de uma chamada: "1º e 2º tempo", "1º ao 4º
 * tempo", "3º tempo".
 *
 * Mora aqui e não repetido nas três telas (listagem, detalhe e dialog)
 * porque é a frase que diz ao professor o que ele está lançando — duas
 * redações divergiriam no dia em que uma mudar.
 */
export function descreverTempos(tempos: number[]): string {
  if (tempos.length === 0) return "—";
  const ordenados = [...tempos].sort((a, b) => a - b);
  if (ordenados.length === 1) return `${ordenados[0]}º tempo`;

  // Bloco contíguo vira intervalo; o resto sai enumerado, porque "1º ao
  // 4º" mentiria sobre uma chamada que cobre o 1º e o 4º apenas.
  const contiguo = ordenados.every(
    (ordem, indice) => indice === 0 || ordem === ordenados[indice - 1] + 1,
  );
  if (contiguo && ordenados.length > 2) {
    return `${ordenados[0]}º ao ${ordenados[ordenados.length - 1]}º tempo`;
  }
  const ultimo = ordenados[ordenados.length - 1];
  const anteriores = ordenados.slice(0, -1).map((ordem) => `${ordem}º`);
  return `${anteriores.join(", ")} e ${ultimo}º tempo`;
}

/**
 * Faixa de horário coberta pelo bloco: "07:00–08:40".
 *
 * Vazio quando o catálogo não tem mais aquele tempo — o registro guarda o
 * ordinal, não o horário (ver `PRESENCA.md`), então uma chamada antiga
 * pode apontar pra um tempo que a escola removeu. Nesse caso a tela mostra
 * só o ordinal, que é o dado que existe.
 */
export function faixaDeHorario(detalhe: TempoDetalhe[]): string {
  const comHorario = detalhe.filter((item) => item.hora_inicio && item.hora_fim);
  if (comHorario.length === 0) return "";
  const inicio = horaCurta(comHorario[0].hora_inicio);
  const fim = horaCurta(comHorario[comHorario.length - 1].hora_fim);
  return `${inicio}–${fim}`;
}

/**
 * Linha que identifica a aula de uma chamada: disciplina e bloco.
 *
 * Existe porque a chamada deixou de ser uma por dia: a turma agora tem
 * várias no mesmo dia, e sem isto a listagem mostraria linhas idênticas.
 */
export function descreverAula(registro: RegistroPresenca): string {
  const bloco = descreverTempos(registro.tempos);
  if (!registro.disciplina_nome) return bloco;
  return `${registro.disciplina_nome} · ${bloco}`;
}
