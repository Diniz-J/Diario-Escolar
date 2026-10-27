import axios from "axios";
import { useState, type FormEvent } from "react";

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
import { usePermissoes } from "@/features/auth/usePermissoes";
import { useTurmas } from "@/features/turmas/hooks";
import { hojeISO } from "@/lib/datas";
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
  // `escola` no payload SÓ pra admin global — derivada da turma.
  // Outros perfis: backend deduz via JWT.
  const { ehAdminGlobal } = usePermissoes();
  const turmasQuery = useTurmas();
  const createMutation = useCreateRegistro();

  const hoje = hojeISO();

  // `turmaId` guarda só a escolha explícita; o valor que vale é o
  // derivado abaixo. A lista de turmas chega depois do mount, e
  // sincronizá-la com `setState` num efeito é o que a regra
  // `react-hooks/set-state-in-effect` acusa. A data nasce de `hoje`
  // porque a página remonta o dialog (`key={formKey}`) a cada abertura.
  const [turmaId, setTurmaId] = useState("");
  const [data, setData] = useState(hoje);
  const [erro, setErro] = useState<string | null>(null);

  // Se há uma única turma, ela entra sozinha quando a lista chega.
  const turmas = turmasQuery.data;
  const turmaEfetiva =
    turmaId || (turmas?.length === 1 ? String(turmas[0].id) : "");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro(null);

    const turma = turmasQuery.data?.find(
      (t) => String(t.id) === turmaEfetiva,
    );
    if (!turma) {
      setErro("Selecione uma turma.");
      return;
    }

    const payload: RegistroPresencaInput = {
      // `escola` deduzida pelo backend quando o user tem escola no perfil.
      ...(ehAdminGlobal ? { escola: turma.escola } : {}),
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
          <DialogTitle className="font-heading tracking-tight">
            Nova chamada
          </DialogTitle>
          <DialogDescription>
            Os alunos ativos da turma serão adicionados automaticamente
            como presentes; você ajusta os ausentes na tela seguinte.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
              Turma
            </Label>
            <Select value={turmaEfetiva} onValueChange={setTurmaId}>
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
            <Label
              htmlFor="data"
              className="text-[11px] uppercase tracking-[0.18em] text-sepia"
            >
              Data
            </Label>
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
              variant="ghost"
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
