import axios from "axios";
import { useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import type { RegistroAulaInput } from "@/types/api";

import {
  useCreateRegistroAula,
  useRegistroAula,
  useUpdateRegistroAula,
} from "./hooks";

interface RegistroAulaFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  // Contexto da aula (vem do slot escolhido na agenda).
  turma: number;
  disciplina: number;
  professor: number;
  data: string; // YYYY-MM-DD
  // Quando o slot já tem registro, edita; senão cria.
  registroId?: number | null;
  // Texto descritivo do dia/turma/disciplina pro cabeçalho do dialog.
  contextoLabel?: string;
}

export function RegistroAulaFormDialog({
  open,
  onOpenChange,
  turma,
  disciplina,
  professor,
  data,
  registroId,
  contextoLabel,
}: RegistroAulaFormDialogProps) {
  const editando = registroId != null;
  const registroQuery = useRegistroAula(editando ? registroId : undefined);
  const createMutation = useCreateRegistroAula();
  const updateMutation = useUpdateRegistroAula();

  const [conteudo, setConteudo] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  const registro = registroQuery.data;
  // Aula conferida pela direção é só leitura — o professor não reabre.
  const somenteLeitura = registro?.status === "conferido";

  useEffect(() => {
    if (open) {
      setErro(null);
      setConteudo(editando ? (registro?.conteudo ?? "") : "");
    }
  }, [open, editando, registro?.conteudo]);

  const enviando = createMutation.isPending || updateMutation.isPending;

  async function salvar(status: "rascunho" | "lancado") {
    setErro(null);
    if (status === "lancado" && !conteudo.trim()) {
      setErro("Escreva o conteúdo antes de lançar a aula.");
      return;
    }
    const payload: RegistroAulaInput = {
      turma,
      disciplina,
      professor,
      data,
      conteudo,
      status,
    };
    try {
      if (editando && registroId != null) {
        await updateMutation.mutateAsync({ id: registroId, patch: payload });
      } else {
        await createMutation.mutateAsync(payload);
      }
      onOpenChange(false);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data) {
        const dados = err.response.data as Record<string, unknown>;
        const primeira = Object.values(dados)
          .flat()
          .find((v): v is string => typeof v === "string");
        setErro(primeira ?? "Não foi possível salvar.");
      } else {
        setErro("Erro inesperado.");
        console.error(err);
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            {somenteLeitura ? "Aula conferida" : "Conteúdo da aula"}
          </DialogTitle>
          <DialogDescription>
            {contextoLabel}
            {somenteLeitura
              ? " — já conferida pela direção, somente leitura."
              : null}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label
            htmlFor="conteudo"
            className="text-[11px] uppercase tracking-[0.18em] text-sepia"
          >
            Conteúdo programático ministrado
          </Label>
          <textarea
            id="conteudo"
            rows={8}
            value={conteudo}
            disabled={somenteLeitura || registroQuery.isLoading}
            onChange={(e) => setConteudo(e.target.value)}
            className="w-full rounded-md border border-border bg-paper px-3 py-2 text-sm focus:outline-none focus:border-ferrugem focus:ring-2 focus:ring-ferrugem/20 transition resize-y disabled:opacity-70"
            placeholder="O que foi trabalhado nesta aula?"
          />
        </div>

        {erro && (
          <Alert variant="destructive">
            <AlertDescription>{erro}</AlertDescription>
          </Alert>
        )}

        <DialogFooter>
          <Button
            type="button"
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={enviando}
          >
            {somenteLeitura ? "Fechar" : "Cancelar"}
          </Button>
          {!somenteLeitura && (
            <>
              <Button
                type="button"
                variant="outline"
                onClick={() => salvar("rascunho")}
                disabled={enviando}
              >
                Salvar rascunho
              </Button>
              <Button
                type="button"
                onClick={() => salvar("lancado")}
                disabled={enviando}
              >
                {enviando ? "Salvando..." : "Lançar"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
