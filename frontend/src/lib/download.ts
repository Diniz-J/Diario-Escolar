import { api } from "@/lib/api";

// Download de arquivo autenticado.
//
// Não dá pra apontar `window.location` pro endpoint: o Bearer vive em
// memória/localStorage e é o interceptor do axios que o injeta, então a
// navegação direta sairia sem auth e tomaria 401. O jeito é baixar como
// Blob e simular um clique num `<a download>`.
//
// `nomeCustomizado` (sem extensão) sobrescreve o nome sugerido pelo
// backend no `Content-Disposition`; sem ele, vale o do backend.
//
// Nasceu duplicado em features/boletins e features/aulas; virou módulo
// quando o relatório de frequência ficou sendo o terceiro a precisar.
export async function baixarArquivo(
  url: string,
  params: Record<string, unknown>,
  extensao?: string,
  nomeCustomizado?: string,
): Promise<void> {
  let resp;
  try {
    resp = await api.get(url, { params, responseType: "blob" });
  } catch (erro) {
    throw await comoErroLegivel(erro);
  }
  // Content-Disposition vem do backend: `attachment; filename="..."`.
  const disp = resp.headers["content-disposition"] as string | undefined;
  const matchNome = disp?.match(/filename="?([^"]+)"?/);
  const nomeDoBackend = matchNome ? matchNome[1] : "download";
  const nomeFinal = nomeCustomizado
    ? `${nomeCustomizado}${extensao ?? ""}`
    : nomeDoBackend;
  const blobUrl = URL.createObjectURL(resp.data as Blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = nomeFinal;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Libera memória depois de um tick.
  setTimeout(() => URL.revokeObjectURL(blobUrl), 0);
}

// `responseType: "blob"` vale também pro corpo de ERRO: um 400 com
// `{"detail": "..."}` chega como Blob, e ler `response.data.detail`
// devolveria undefined. Sem isto, a mensagem que o backend escreveu pra
// explicar o que fazer (estreitar o filtro, trocar de formato) nunca
// chegaria na tela.
async function comoErroLegivel(erro: unknown): Promise<Error> {
  const corpo = (erro as { response?: { data?: unknown } })?.response?.data;
  if (corpo instanceof Blob) {
    try {
      const texto = await corpo.text();
      const dados = JSON.parse(texto) as { detail?: string };
      if (dados?.detail) return new Error(dados.detail);
    } catch {
      // Corpo que não é JSON (HTML de erro, resposta truncada): cai no
      // erro original, que o chamador trata com mensagem genérica.
    }
  }
  return erro instanceof Error ? erro : new Error(String(erro));
}
