import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface NomeArquivoDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  // Nome default mostrado no input (sem extensão). Ex.: "boletim_2026001_anual".
  nomeDefault: string;
  // Extensão exibida ao lado do input pra dar contexto visual. Ex.: ".pdf".
  extensao: string;
  // Título e descrição contextualizam o tipo de export (PDF/CSV/XLSX).
  titulo: string;
  descricao?: string;
  enviando?: boolean;
  // Callback recebe o nome final SEM extensão. O hook chamador concatena
  // ao baixar (e o backend já manda extensão correta no MIME type).
  onConfirmar: (nome: string) => void;
}

// Dialog reusável pra escolher o nome do arquivo antes do download.
// Pré-preenche com o nome sugerido pelo backend e aceita edição
// — caractéres inválidos pra filesystem (`/\<>:"|?*`) são removidos
// na hora de baixar.
export function NomeArquivoDialog({
  open,
  onOpenChange,
  nomeDefault,
  extensao,
  titulo,
  descricao,
  enviando = false,
  onConfirmar,
}: NomeArquivoDialogProps) {
  const [nome, setNome] = useState(nomeDefault);

  // Re-sincroniza quando o dialog reabre com um default diferente
  // (ex.: trocou de período).
  useEffect(() => {
    if (open) setNome(nomeDefault);
  }, [open, nomeDefault]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // Higieniza: remove chars proibidos em nomes de arquivo no
    // Windows/Linux/macOS. Tira whitespace nas pontas.
    const limpo = nome.replace(/[/\\<>:"|?*\x00-\x1F]/g, "").trim();
    onConfirmar(limpo || nomeDefault);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            {titulo}
          </DialogTitle>
          {descricao && <DialogDescription>{descricao}</DialogDescription>}
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label
              htmlFor="nome-arquivo"
              className="text-[11px] uppercase tracking-[0.18em] text-sepia"
            >
              Nome do arquivo
            </Label>
            <div className="flex items-center gap-2">
              <Input
                id="nome-arquivo"
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                autoFocus
                className="flex-1"
              />
              <span className="text-sm text-sepia font-mono">{extensao}</span>
            </div>
            <p className="text-[10px] text-sepia/70">
              Caracteres inválidos pra arquivo são removidos
              automaticamente.
            </p>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              disabled={enviando}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={enviando || !nome.trim()}>
              {enviando ? "Gerando..." : "Baixar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
