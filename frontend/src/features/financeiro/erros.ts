import axios from "axios";

// Extrai a primeira mensagem útil de um erro do DRF.
//
// Mora num módulo próprio porque os três dialogs do financeiro precisam
// dela e as mensagens aqui são o canal real de comunicação das
// invariantes: "este aluno já tem fatura na competência 03/2026",
// "vigência sobreposta", "fatura cancelada não recebe pagamento". Engolir
// isso e mostrar "erro ao salvar" esconderia exatamente o que a secretaria
// precisa ler.
export function mensagemDeErro(err: unknown, fallback: string): string {
  if (!axios.isAxiosError(err) || !err.response?.data) {
    console.error(err);
    return fallback;
  }
  const dados = err.response.data as Record<string, unknown>;
  const primeira = Object.values(dados)
    .flat()
    .find((v): v is string => typeof v === "string");
  return primeira ?? fallback;
}
