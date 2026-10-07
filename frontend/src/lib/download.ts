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
  const resp = await api.get(url, { params, responseType: "blob" });
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
