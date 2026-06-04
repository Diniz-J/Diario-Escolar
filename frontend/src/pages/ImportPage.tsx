import axios from "axios";
import { useMemo, useState, type ChangeEvent, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ENTIDADES,
  useBaixarTemplate,
  useExportar,
  useImportar,
  type EntidadeImportExport,
  type ImportResultado,
} from "@/features/import-export/hooks";

// Página /import — admin-only.
//
// Fluxo:
// 1. Usuário escolhe a entidade e o arquivo (CSV ou XLSX).
// 2. Botão "Pré-visualizar" dispara o backend em dry-run — savepoint
//    rola back qualquer side-effect (inclusive turma criada na hora).
// 3. Painel mostra `criados`, `pulados` e `erros` por linha.
// 4. Se sem erros, botão "Confirmar e salvar" persiste.
// 5. "Baixar modelo" devolve o template (só cabeçalhos) pra
//    o usuário preencher offline.
// 6. "Exportar" devolve os dados atuais escopados à escola.
export function ImportPage() {
  const [entidade, setEntidade] = useState<EntidadeImportExport>("alunos");
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [turnoPadrao, setTurnoPadrao] = useState("");
  const [anoPadrao, setAnoPadrao] = useState(
    String(new Date().getFullYear()),
  );
  const [resultado, setResultado] = useState<ImportResultado | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const importar = useImportar();
  const baixarTemplate = useBaixarTemplate();
  const exportar = useExportar();

  // Extras só fazem sentido pra alunos (cria turma faltante).
  const mostrarExtras = entidade === "alunos";

  function handleArquivo(event: ChangeEvent<HTMLInputElement>) {
    setArquivo(event.target.files?.[0] ?? null);
    setResultado(null);
    setErro(null);
  }

  async function executar(confirmar: boolean) {
    setErro(null);
    if (!arquivo) {
      setErro("Selecione um arquivo CSV ou XLSX.");
      return;
    }
    try {
      const data = await importar.mutateAsync({
        entidade,
        arquivo,
        confirmar,
        extras: mostrarExtras
          ? { turno_padrao: turnoPadrao, ano_letivo_padrao: anoPadrao }
          : undefined,
      });
      setResultado(data);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data?.detail) {
        setErro(String(err.response.data.detail));
      } else {
        setErro("Não foi possível processar o arquivo.");
        console.error(err);
      }
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void executar(false);
  }

  const semErros = resultado != null && resultado.erros.length === 0;
  const labelEntidade =
    ENTIDADES.find((e) => e.value === entidade)?.label ?? entidade;

  // Quando o resultado é só "preview" mostramos um aviso explícito —
  // evita confusão de "achei que tinha salvado".
  const statusBanner = useMemo(() => {
    if (!resultado) return null;
    if (resultado.persistido) {
      return (
        <p className="text-sm px-3 py-2 rounded-md bg-olive/10 text-olive border border-olive/20">
          {resultado.criados} registros gravados. Pulados:{" "}
          {resultado.pulados.length}.
        </p>
      );
    }
    return (
      <p className="text-sm px-3 py-2 rounded-md bg-paper border border-border text-sepia">
        Pré-visualização — nada foi salvo. {resultado.criados} seriam
        criados, {resultado.pulados.length} pulados.
      </p>
    );
  }, [resultado]);

  return (
    <div className="p-4 md:p-8 space-y-6 max-w-3xl">
      <header className="space-y-3">
        <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
          Importar e exportar
        </h1>
        <div className="h-px w-10 bg-ferrugem" />
        <p className="text-[11px] uppercase tracking-[0.18em] text-sepia">
          Cargas em massa de cadastros — pré-visualizar antes de salvar
        </p>
      </header>

      <form
        onSubmit={handleSubmit}
        className="bg-paper rounded-lg border border-border p-6 space-y-5"
      >
        <div className="space-y-2">
          <Label
            htmlFor="entidade"
            className="text-[11px] uppercase tracking-[0.18em] text-sepia"
          >
            Entidade
          </Label>
          <Select
            value={entidade}
            onValueChange={(v) => setEntidade(v as EntidadeImportExport)}
          >
            <SelectTrigger id="entidade" className="bg-paper">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ENTIDADES.map((e) => (
                <SelectItem key={e.value} value={e.value}>
                  {e.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label
            htmlFor="arquivo"
            className="text-[11px] uppercase tracking-[0.18em] text-sepia"
          >
            Arquivo (CSV ou XLSX)
          </Label>
          <input
            id="arquivo"
            type="file"
            accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={handleArquivo}
            className="block w-full text-sm text-tinta file:mr-3 file:py-2 file:px-3 file:rounded-md file:border file:border-border file:bg-paper file:text-tinta hover:file:bg-linho file:cursor-pointer"
          />
          {arquivo && (
            <p className="text-[11px] text-sepia">
              {arquivo.name} · {(arquivo.size / 1024).toFixed(1)} KB
            </p>
          )}
        </div>

        {mostrarExtras && (
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label
                htmlFor="turno-padrao"
                className="text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Turno padrão (turmas novas)
              </Label>
              <Select value={turnoPadrao} onValueChange={setTurnoPadrao}>
                <SelectTrigger id="turno-padrao" className="bg-paper">
                  <SelectValue placeholder="Opcional" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="matutino">Matutino</SelectItem>
                  <SelectItem value="vespertino">Vespertino</SelectItem>
                  <SelectItem value="noturno">Noturno</SelectItem>
                  <SelectItem value="integral">Integral</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label
                htmlFor="ano-padrao"
                className="text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Ano letivo padrão
              </Label>
              <Input
                id="ano-padrao"
                type="number"
                min={1900}
                max={2100}
                value={anoPadrao}
                onChange={(e) => setAnoPadrao(e.target.value)}
              />
            </div>
          </div>
        )}

        {erro && (
          <p className="text-sm px-3 py-2 rounded-md bg-destructive/15 text-destructive border border-destructive/30">
            {erro}
          </p>
        )}

        <div className="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between pt-2">
          <div className="flex gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() =>
                baixarTemplate.mutate({ entidade, formato: "csv" })
              }
              disabled={baixarTemplate.isPending}
            >
              Baixar modelo CSV
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() =>
                exportar.mutate({ entidade, formato: "csv" })
              }
              disabled={exportar.isPending}
            >
              Exportar atual
            </Button>
          </div>
          <div className="flex gap-3">
            <Button type="submit" variant="outline" disabled={importar.isPending}>
              {importar.isPending && !resultado?.persistido
                ? "Analisando..."
                : "Pré-visualizar"}
            </Button>
            <Button
              type="button"
              disabled={!semErros || importar.isPending}
              onClick={() => void executar(true)}
            >
              {importar.isPending && resultado != null
                ? "Salvando..."
                : "Confirmar e salvar"}
            </Button>
          </div>
        </div>
      </form>

      {resultado && (
        <section className="space-y-4">
          <h2 className="font-heading text-lg tracking-tight">
            Resultado — {labelEntidade}
          </h2>

          {statusBanner}

          {resultado.erros.length > 0 && (
            <div className="bg-paper rounded-lg border border-border overflow-hidden">
              <div className="px-4 py-3 border-b border-border">
                <p className="text-[11px] uppercase tracking-[0.18em] text-destructive">
                  {resultado.erros.length} erros — corrija e re-envie
                </p>
              </div>
              <ul className="divide-y divide-border">
                {resultado.erros.map((e, idx) => (
                  <li key={idx} className="px-4 py-2 text-sm">
                    <span className="text-[11px] uppercase tracking-wide text-sepia mr-2">
                      {e.linha != null ? `Linha ${e.linha}` : "Arquivo"}
                    </span>
                    <span>{e.mensagem}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {resultado.pulados.length > 0 && (
            <div className="bg-paper rounded-lg border border-border overflow-hidden">
              <div className="px-4 py-3 border-b border-border">
                <p className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                  {resultado.pulados.length} pulados — já existiam
                </p>
              </div>
              <ul className="divide-y divide-border">
                {resultado.pulados.slice(0, 20).map((p, idx) => (
                  <li key={idx} className="px-4 py-2 text-sm">
                    {p.linha}
                  </li>
                ))}
                {resultado.pulados.length > 20 && (
                  <li className="px-4 py-2 text-[11px] uppercase tracking-wide text-sepia">
                    ... e mais {resultado.pulados.length - 20}
                  </li>
                )}
              </ul>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
