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
  useExportarAlunos,
  type AlunosExportParams,
  type FormatoRelatorio,
} from "./hooks";
import { SeletorFormato } from "./SeletorFormato";

type FiltrosAtivos = Omit<AlunosExportParams, "formato" | "nome">;

interface ExportarAlunosDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  // Filtros server-side que estão valendo na tela que abriu o diálogo.
  filtros: FiltrosAtivos;
  // Descrição legível do recorte, pra conferir antes de baixar.
  recorte: string;
  // Busca da tela, quando houver. É client-side e NÃO entra no arquivo.
  busca?: string;
}

// Exporta a lista cadastral de alunos do recorte atual.
//
// Não repete os filtros: eles já estão na tela. O PDF sai separado por
// turma e serve de lista impressa; CSV e XLSX trazem também o email do
// responsável, pra secretaria trabalhar fora do sistema.
export function ExportarAlunosDialog({
  open,
  onOpenChange,
  filtros,
  recorte,
  busca,
}: ExportarAlunosDialogProps) {
  const [formato, setFormato] = useState<FormatoRelatorio>("pdf");
  const exportar = useExportarAlunos();

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
            Exportar alunos
          </DialogTitle>
          <DialogDescription>
            Lista cadastral com matrícula, nascimento e responsável,
            separada por turma no PDF.
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
              A busca por “{busca}” filtra só a página aberta aqui no
              navegador e
              <strong className="font-medium"> não entra no arquivo</strong>
              , que sai com o recorte inteiro.
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
