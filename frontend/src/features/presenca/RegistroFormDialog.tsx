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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/features/auth/useAuth";
import { useTurmas } from "@/features/turmas/hooks";
import type { RegistroPresencaInput } from "@/types/api";

import { useCreateRegistro } from "./hooks";

interface RegistroFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  // Disparado após criar o registro com sucesso — útil pra navegar
  // pra tela de chamada do novo registro.
  onCreated?: (id: number) => void;
}

// Form de criação de uma chamada. Itens (status por aluno) são gerados
// automaticamente pelo backend no perform_create da view — não enviamos
// itens daqui.
export function RegistroFormDialog({
  open,
  onOpenChange,
  onCreated,
}: RegistroFormDialogProps) {
  const { user } = useAuth();
  const escolaAuto = user?.escola_id ?? null;
  const turmasQuery = useTurmas();
  const createMutation = useCreateRegistro();

  const hoje = new Date().toISOString().slice(0, 10);

  const [turmaId, setTurmaId] = useState("");
  const [data, setData] = useState(hoje);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setErro(null);
      // Se há uma única turma, pré-seleciona.
      const turmas = turmasQuery.data;
      setTurmaId(turmas?.length === 1 ? String(turmas[0].id) : "");
      setData(hoje);
    }
  }, [open, turmasQuery.data, hoje]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro(null);

    const turma = turmasQuery.data?.find((t) => String(t.id) === turmaId);
    if (!turma) {
      setErro("Selecione uma turma.");
      return;
    }

    const payload: RegistroPresencaInput = {
      // `escola` deduzida pelo backend quando o user tem escola no perfil.
      ...(escolaAuto == null ? { escola: turma.escola } : {}),
      turma: turma.id,
      data,
      professor: null,
      observacao: "",
    };

    try {
      const novo = await createMutation.mutateAsync(payload);
      onOpenChange(false);
      onCreated?.(novo.id);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.data) {
        const dataErr = err.response.data as Record<string, unknown>;
        const primeiraMsg = Object.values(dataErr)
          .flat()
          .find((v): v is string => typeof v === "string");
        setErro(primeiraMsg ?? "Não foi possível criar a chamada.");
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
          <DialogTitle>Nova chamada</DialogTitle>
          <DialogDescription>
            Os alunos ativos da turma serão adicionados automaticamente
            como presentes; você ajusta os ausentes na tela seguinte.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label>Turma</Label>
            <Select value={turmaId} onValueChange={setTurmaId}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Selecione uma turma" />
              </SelectTrigger>
              <SelectContent>
                {turmasQuery.data?.map((t) => (
                  <SelectItem key={t.id} value={String(t.id)}>
                    {t.nome} — {t.turno_display} {t.ano_letivo}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="data">Data</Label>
            <Input
              id="data"
              type="date"
              required
              max={hoje}
              value={data}
              onChange={(e) => setData(e.target.value)}
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
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={createMutation.isPending}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Criando..." : "Abrir chamada"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
