import type { Turno } from "@/types/api";

// 0=segunda ... 6=domingo, alinhado com `date.weekday()` do Python e com
// o enum `Lecionamento.DiaSemana` do backend.
export const DIAS_SEMANA: { valor: number; label: string; curto: string }[] = [
  { valor: 0, label: "Segunda", curto: "Seg" },
  { valor: 1, label: "Terça", curto: "Ter" },
  { valor: 2, label: "Quarta", curto: "Qua" },
  { valor: 3, label: "Quinta", curto: "Qui" },
  { valor: 4, label: "Sexta", curto: "Sex" },
  { valor: 5, label: "Sábado", curto: "Sáb" },
  { valor: 6, label: "Domingo", curto: "Dom" },
];

// A semana útil é a base da matriz; sábado e domingo entram só quando a
// escola usa (ver `GradePage`).
export const DIAS_UTEIS = [0, 1, 2, 3, 4];

export const TURNOS: { value: Turno; label: string }[] = [
  { value: "matutino", label: "Matutino" },
  { value: "vespertino", label: "Vespertino" },
  { value: "noturno", label: "Noturno" },
  { value: "integral", label: "Integral" },
];

// `TimeField` do DRF chega como "07:00:00"; a grade só mostra hora e
// minuto. Split em vez de `new Date`, pelo mesmo motivo de `lib/datas.ts`:
// não existe data aqui pra ancorar o fuso, e montar uma inventaria um.
export function horaCurta(hora: string | null | undefined): string {
  if (!hora) return "";
  const [h, m] = hora.split(":");
  return h && m ? `${h}:${m}` : hora;
}

export function nomeDiaSemana(valor: number): string {
  return DIAS_SEMANA.find((d) => d.valor === valor)?.label ?? `Dia ${valor}`;
}
