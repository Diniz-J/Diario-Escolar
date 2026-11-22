import axios from "axios";
import { useState } from "react";

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
import { useTurmas } from "@/features/turmas/hooks";
import type { ClonagemResultado, Turma } from "@/types/api";

import { nomeDiaSemana } from "./constants";
import { useClonarGrade } from "./hooks";

const LABEL = "text-[11px] uppercase tracking-[0.18em] text-sepia";

interface ClonarGradeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  turmaDestino: Turma;
}

// Copia a grade de outra turma pra esta — o atalho da virada de ano, que
// é quando a grade inteira precisa ser remontada. O resultado fica no
// dialog em vez de ir pra toast: o backend reporta o que foi ignorado
// (professor que não leciona mais aquela matéria na turma nova), e essa
// lista é o que a direção precisa conferir antes de fechar.
export function ClonarGradeDialog({
  open,
  onOpenChange,
  turmaDestino,
}: ClonarGradeDialogProps) {
  const turmasQuery = useTurmas();
  const clonarMutation = useClonarGrade();

  const [origemId, setOrigemId] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [resultado, setResultado] = useState<ClonagemResultado | null>(null);

  const origens = (turmasQuery.data ?? []).filter(
    (t) => t.id !== turmaDestino.id,
  );
  const falhouCarregar = turmasQuery.isError;

  async function clonar() {
    setErro(null);
    if (!origemId) {
      setErro("Selecione a turma de origem.");
      return;
    }
    try {
      const dados = await clonarMutation.mutateAsync({
        turma_origem: parseInt(origemId, 10),
        turma_destino: turmaDestino.id,
      });
      setResultado(dados);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data) {
        const data = err.response.data as Record<string, unknown>;
        const primeiraMsg = Object.values(data)
          .flat()
          .find((v): v is string => typeof v === "string");
        setErro(primeiraMsg ?? "Não foi possível clonar.");
      } else {
        setErro("Erro inesperado.");
        console.error(err);
      }
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            Clonar grade
          </DialogTitle>
          <DialogDescription>
            Copia os horários de outra turma para {turmaDestino.nome}. Só
            funciona com a grade desta turma vazia.
          </DialogDescription>
        </DialogHeader>

        {resultado ? (
          <div className="space-y-4">
            <p className="text-sm text-tinta">
              {resultado.criados === 0
                ? "Nenhum horário foi copiado."
                : `${resultado.criados} ${
                    resultado.criados === 1 ? "horário" : "horários"
                  } copiado${resultado.criados === 1 ? "" : "s"}.`}
            </p>
            {resultado.ignorados.length > 0 && (
              <div className="space-y-2">
                <p className={LABEL}>Não copiados</p>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  {resultado.ignorados.map((item, indice) => (
                    <li
                      key={`${item.dia_semana}-${item.tempo_ordem}-${indice}`}
                      className="rounded border border-border bg-paper p-2"
                    >
                      <span className="text-tinta">
                        {nomeDiaSemana(item.dia_semana)}, {item.tempo_ordem}º
                        tempo
                      </span>
                      <br />
                      {item.motivo}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <DialogFooter>
              <Button type="button" onClick={() => onOpenChange(false)}>
                Fechar
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className={LABEL}>Copiar de</Label>
              <Select value={origemId} onValueChange={setOrigemId}>
                <SelectTrigger>
                  <SelectValue placeholder="Selecione a turma" />
                </SelectTrigger>
                <SelectContent>
                  {origens.map((turma) => (
                    <SelectItem key={turma.id} value={String(turma.id)}>
                      {turma.nome} ({turma.ano_letivo})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <p className="text-xs text-muted-foreground">
              Cada aula é recriada com o professor que leciona a mesma
              disciplina nesta turma. O que não tiver equivalente fica de
              fora e aparece listado.
            </p>

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
                disabled={clonarMutation.isPending}
              >
                Cancelar
              </Button>
              <Button
                type="button"
                onClick={clonar}
                disabled={clonarMutation.isPending || falhouCarregar}
              >
                {clonarMutation.isPending ? "Clonando..." : "Clonar"}
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
