import axios from "axios";
import { useState, type FormEvent } from "react";

import { AlertaOpcoesIndisponiveis } from "@/components/AlertaOpcoesIndisponiveis";
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
import { useLecionamentos } from "@/features/lecionamentos/hooks";
import { useProfessores } from "@/features/professores/hooks";
import type { AulaGradeInput, TempoAula } from "@/types/api";

import { horaCurta, nomeDiaSemana } from "./constants";
import { useCreateSlot } from "./hooks";

const LABEL = "text-[11px] uppercase tracking-[0.18em] text-sepia";

interface SlotFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  turmaId: number;
  diaSemana: number;
  tempo: TempoAula;
}

// Preenche uma célula da grade: escolhe qual lecionamento da turma ocupa
// aquele dia e tempo. A lista vem dos lecionamentos **da própria turma** —
// o backend exige que o slot aponte pra um vínculo existente, então
// oferecer a escola inteira daria opção que ele recusa.
export function SlotFormDialog({
  open,
  onOpenChange,
  turmaId,
  diaSemana,
  tempo,
}: SlotFormDialogProps) {
  const lecionamentosQuery = useLecionamentos({ turma: turmaId, ativo: true });
  const disciplinasQuery = useDisciplinas();
  const professoresQuery = useProfessores();
  const createMutation = useCreateSlot();

  const [lecionamentoId, setLecionamentoId] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  const lecionamentos = lecionamentosQuery.data ?? [];
  // O select de lecionamento é obrigatório na validação de submit: sem a
  // lista não há o que escolher, e a falha de rede não pode virar
  // "Selecione uma aula" (que culparia o usuário).
  const falhouCarregar =
    lecionamentosQuery.isError ||
    disciplinasQuery.isError ||
    professoresQuery.isError;

  function rotulo(lecionamentoId: number): string {
    const lec = lecionamentos.find((l) => l.id === lecionamentoId);
    if (!lec) return `Lecionamento #${lecionamentoId}`;
    const disciplina =
      disciplinasQuery.data?.find((d) => d.id === lec.disciplina)?.nome ??
      `Disciplina #${lec.disciplina}`;
    const professor = professoresQuery.data?.find((p) => p.id === lec.professor);
    const nome = professor?.nome_completo ?? `Professor #${lec.professor}`;
    return `${disciplina} — ${nome}`;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro(null);

    if (!lecionamentoId) {
      setErro("Selecione a disciplina e o professor desta aula.");
      return;
    }

    const payload: AulaGradeInput = {
      // `turma` não vai no payload: o backend a deriva do lecionamento.
      lecionamento: parseInt(lecionamentoId, 10),
      dia_semana: diaSemana,
      tempo: tempo.id,
    };

    try {
      await createMutation.mutateAsync(payload);
      onOpenChange(false);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data) {
        const data = err.response.data as Record<string, unknown>;
        const primeiraMsg = Object.values(data)
          .flat()
          .find((v): v is string => typeof v === "string");
        setErro(primeiraMsg ?? "Não foi possível salvar.");
      } else {
        setErro("Erro inesperado.");
        console.error(err);
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            Aula de {nomeDiaSemana(diaSemana).toLowerCase()}
          </DialogTitle>
          <DialogDescription>
            {tempo.ordem}º tempo, {horaCurta(tempo.hora_inicio)} às{" "}
            {horaCurta(tempo.hora_fim)}.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label className={LABEL}>Disciplina e professor</Label>
            <Select value={lecionamentoId} onValueChange={setLecionamentoId}>
              <SelectTrigger>
                <SelectValue placeholder="Selecione" />
              </SelectTrigger>
              <SelectContent>
                {lecionamentos.map((lec) => (
                  <SelectItem key={lec.id} value={String(lec.id)}>
                    {rotulo(lec.id)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {!falhouCarregar && lecionamentos.length === 0 && (
              <p className="text-xs text-muted-foreground">
                Esta turma não tem lecionamento ativo. Cadastre quem leciona
                cada disciplina na ficha do professor antes de montar a grade.
              </p>
            )}
          </div>

          <AlertaOpcoesIndisponiveis falhou={falhouCarregar} />

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
              disabled={createMutation.isPending}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={createMutation.isPending || falhouCarregar}
            >
              {createMutation.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
