import axios from "axios";
import { useEffect, useState, type FormEvent } from "react";

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useDisciplinas } from "@/features/disciplinas/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import type { PlanoEnsinoInput } from "@/types/api";

import { useCreatePlanoEnsino } from "./hooks";

interface PlanoEnsinoCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  // Dispara quando criar com sucesso — usado pra navegar pro detalhe
  // do plano novo e o usuário já preencher o conteúdo.
  onCreated?: (planoId: number) => void;
}

// Dialog enxuto que cria a "casca" do plano (turma + disciplina + ano).
// Os campos longos (ementa, conteúdo programático, objetivos, etc.) são
// preenchidos na tela de detalhe — não fazem sentido aqui.
export function PlanoEnsinoCreateDialog({
  open,
  onOpenChange,
  onCreated,
}: PlanoEnsinoCreateDialogProps) {
  const turmasQuery = useTurmas();
  const disciplinasQuery = useDisciplinas();
  const createMutation = useCreatePlanoEnsino();

  const [turmaId, setTurmaId] = useState("");
  const [disciplinaId, setDisciplinaId] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setErro(null);
      setTurmaId("");
      setDisciplinaId("");
    }
  }, [open]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro(null);

    const turma = turmasQuery.data?.find((t) => String(t.id) === turmaId);
    const disciplina = disciplinasQuery.data?.find(
      (d) => String(d.id) === disciplinaId,
    );
    if (!turma) {
      setErro("Selecione uma turma.");
      return;
    }
    if (!disciplina) {
      setErro("Selecione uma disciplina.");
      return;
    }

    // `ano_letivo` é derivado da turma — backend exige que coincidam.
    const payload: PlanoEnsinoInput = {
      escola: turma.escola,
      turma: turma.id,
      disciplina: disciplina.id,
      professor: null,
      ano_letivo: turma.ano_letivo,
      ementa: "",
      conteudo_programatico: "",
      objetivos_gerais: "",
      objetivos_especificos: "",
      habilidades_bncc: "",
      carga_horaria: null,
      metodologia: "",
      recursos: "",
      avaliacao: "",
      ativo: true,
    };

    try {
      const plano = await createMutation.mutateAsync(payload);
      onOpenChange(false);
      onCreated?.(plano.id);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data) {
        const data = err.response.data as Record<string, unknown>;
        const primeiraMsg = Object.values(data)
          .flat()
          .find((v): v is string => typeof v === "string");
        setErro(primeiraMsg ?? "Não foi possível criar o plano.");
      } else {
        setErro("Erro inesperado.");
        console.error(err);
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Novo plano de ensino</DialogTitle>
          <DialogDescription>
            Escolha turma e disciplina. Os campos do plano (ementa,
            conteúdo, objetivos, etc.) são preenchidos na tela seguinte.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label>Turma</Label>
            <Select value={turmaId} onValueChange={setTurmaId}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Selecione" />
              </SelectTrigger>
              <SelectContent>
                {turmasQuery.data?.map((t) => (
                  <SelectItem key={t.id} value={String(t.id)}>
                    {t.nome} — {t.ano_letivo}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Disciplina</Label>
            <Select value={disciplinaId} onValueChange={setDisciplinaId}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Selecione" />
              </SelectTrigger>
              <SelectContent>
                {disciplinasQuery.data?.map((d) => (
                  <SelectItem key={d.id} value={String(d.id)}>
                    {d.nome}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {erro && (
            <Alert variant="destructive">
              <AlertDescription>{erro}</AlertDescription>
            </Alert>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={createMutation.isPending}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Criando..." : "Criar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
