import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import {
  useExportarOcorrencias,
  type FormatoRelatorio,
  type OcorrenciasExportParams,
} from "./hooks";
import { SeletorFormato } from "./SeletorFormato";

type FiltrosAtivos = Omit<OcorrenciasExportParams, "formato" | "nome">;

interface ExportarOcorrenciasDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  // Filtros server-side que estão valendo na listagem.
  filtros: FiltrosAtivos;
  // Descrição legível do recorte, pra pessoa conferir antes de baixar.
  recorte: string;
  // Texto da busca da tela, quando houver. É client-side e NÃO entra no
  // arquivo — avisamos em vez de deixar a pessoa descobrir abrindo.
  busca?: string;
}

// Exporta o recorte atual da listagem de ocorrências.
//
// Não repete os filtros: eles já estão na tela, e um segundo formulário
// seria uma chance a mais de o arquivo sair diferente do que a pessoa
// está vendo. O diálogo só confirma o recorte e pergunta o formato.
export function ExportarOcorrenciasDialog({
  open,
  onOpenChange,
  filtros,
  recorte,
  busca,
}: ExportarOcorrenciasDialogProps) {
  const [formato, setFormato] = useState<FormatoRelatorio>("pdf");
  const exportar = useExportarOcorrencias();

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    exportar.mutate(
      { ...filtros, formato },
      { onSuccess: () => onOpenChange(false) },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            Exportar ocorrências
          </DialogTitle>
          <DialogDescription>
            Sai o mesmo recorte que está na tela, agrupado por aluno no
            PDF.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <span className="block text-[11px] uppercase tracking-[0.18em] text-sepia">
              Recorte
            </span>
            <p className="text-sm text-tinta">{recorte}</p>
          </div>

          {busca && (
            <p className="rounded-md bg-muted px-3 py-2 text-[11px] leading-relaxed text-sepia">
              A busca por “{busca}” filtra a tabela aqui no navegador e
              <strong className="font-medium"> não entra no arquivo</strong>
              . Pra recortar o arquivo, use status e período.
            </p>
          )}

          <SeletorFormato valor={formato} onChange={setFormato} />

          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              disabled={exportar.isPending}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={exportar.isPending}>
              {exportar.isPending ? "Gerando..." : "Baixar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
