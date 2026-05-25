// Helpers de data — mediam entre o formato ISO usado pelo backend
// (`YYYY-MM-DD`) e o formato brasileiro mostrado ao usuário (`dd/mm/aaaa`).
// Mantemos a UI 100% em pt-BR; ninguém precisa saber o formato cru.

/**
 * Converte uma data ISO (`YYYY-MM-DD`) para o formato pt-BR
 * (`dd/mm/aaaa`). Aceita strings vazias e retorna "".
 */
export function isoToBr(iso: string): string {
  if (!iso) return "";
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return iso;
  const [, ano, mes, dia] = m;
  return `${dia}/${mes}/${ano}`;
}

/**
 * Tenta converter uma string pt-BR num prefixo ISO útil pra busca.
 * Aceita formatos parciais:
 *
 * - `22/05/2026` → `2026-05-22`
 * - `22/05`      → `-05-22`     (prefixo de mês + dia, para qualquer ano)
 * - `2026`       → `2026`
 *
 * Retorna `null` quando a entrada não parece data. O chamador usa o
 * resultado como prefixo para `String.startsWith` ou `includes` numa
 * data ISO.
 */
export function brToIso(input: string): string | null {
  const q = input.trim();
  if (!q) return null;

  // dd/mm/aaaa
  let m = q.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
  if (m) {
    const [, dia, mes, ano] = m;
    return `${ano}-${mes.padStart(2, "0")}-${dia.padStart(2, "0")}`;
  }

  // dd/mm  →  substring com mês e dia (busca por ocorrência em
  // qualquer ano); retornamos só a parte "-MM-DD" que aparece no meio
  // de uma data ISO completa.
  m = q.match(/^(\d{1,2})\/(\d{1,2})$/);
  if (m) {
    const [, dia, mes] = m;
    return `-${mes.padStart(2, "0")}-${dia.padStart(2, "0")}`;
  }

  // ano puro
  if (/^\d{4}$/.test(q)) return q;

  return null;
}
