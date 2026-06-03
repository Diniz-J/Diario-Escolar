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
import { useDisciplinas } from "@/features/disciplinas/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import type { Tarefa, TarefaInput } from "@/types/api";

import { useCreateTarefa, useUpdateTarefa } from "./hooks";

interface TarefaFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tarefa?: Tarefa | null;
}

export function TarefaFormDialog({
  open,
  onOpenChange,
  tarefa,
}: TarefaFormDialogProps) {
  const { user } = useAuth();
  const escolaAuto = user?.escola_id ?? null;
  const turmasQuery = useTurmas();
  const disciplinasQuery = useDisciplinas();
  const createMutation = useCreateTarefa();
  const updateMutation = useUpdateTarefa();

  const editando = tarefa != null;
  const hoje = new Date().toISOString().slice(0, 10);

  const [titulo, setTitulo] = useState("");
  const [descricao, setDescricao] = useState("");
  const [turmaId, setTurmaId] = useState("");
  const [disciplinaId, setDisciplinaId] = useState("");
  const [dataLancamento, setDataLancamento] = useState(hoje);
  const [prazo, setPrazo] = useState("");
  const [valeNota, setValeNota] = useState(false);
  const [notaMaxima, setNotaMaxima] = useState("");
  const [peso, setPeso] = useState("1");
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setErro(null);
      if (tarefa) {
        setTitulo(tarefa.titulo);
        setDescricao(tarefa.descricao);
        setTurmaId(String(tarefa.turma));
        setDisciplinaId(String(tarefa.disciplina));
        setDataLancamento(tarefa.data_lancamento);
        setPrazo(tarefa.prazo ?? "");
        setValeNota(tarefa.vale_nota);
        setNotaMaxima(tarefa.nota_maxima ?? "");
        setPeso(tarefa.peso ?? "1");
      } else {
        setTitulo("");
        setDescricao("");
        setTurmaId("");
        setDisciplinaId("");
        setDataLancamento(hoje);
        setPrazo("");
        setValeNota(false);
        setNotaMaxima("");
        setPeso("1");
      }
    }
  }, [open, tarefa, hoje]);

  const enviando = createMutation.isPending || updateMutation.isPending;

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

    const payload: TarefaInput = {
      // `escola` deduzida pelo backend quando o user tem escola.
      ...(escolaAuto == null ? { escola: turma.escola } : {}),
      turma: turma.id,
      disciplina: disciplina.id,
      professor: null,
      titulo,
      descricao,
      data_lancamento: dataLancamento,
      prazo: prazo || null,
      vale_nota: valeNota,
      nota_maxima: valeNota && notaMaxima ? notaMaxima : null,
      peso: peso || "1",
    };

    try {
      if (editando && tarefa) {
        await updateMutation.mutateAsync({ id: tarefa.id, patch: payload });
      } else {
        await createMutation.mutateAsync(payload);
      }
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
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            {editando ? "Editar tarefa" : "Nova tarefa"}
          </DialogTitle>
          <DialogDescription>
            {editando
              ? "Atualize os dados da tarefa."
              : "Lance uma tarefa para a turma. As entregas dos alunos ativos são criadas automaticamente."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label
              htmlFor="titulo"
              className="text-[11px] uppercase tracking-[0.18em] text-sepia"
            >
              Título
            </Label>
            <Input
              id="titulo"
              required
              value={titulo}
              onChange={(e) => setTitulo(e.target.value)}
              placeholder="Ex.: Lista de exercícios 1"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                Turma
              </Label>
              <Select value={turmaId} onValueChange={setTurmaId}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Selecione" />
                </SelectTrigger>
                <SelectContent>
                  {turmasQuery.data?.map((t) => (
                    <SelectItem key={t.id} value={String(t.id)}>
                      {t.nome}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                Disciplina
              </Label>
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
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label
                htmlFor="data_lancamento"
                className="text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Data de lançamento
              </Label>
              <Input
                id="data_lancamento"
                type="date"
                required
                value={dataLancamento}
                onChange={(e) => setDataLancamento(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label
                htmlFor="prazo"
                className="text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Prazo (opcional)
              </Label>
              <Input
                id="prazo"
                type="date"
                min={dataLancamento}
                value={prazo}
                onChange={(e) => setPrazo(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label
              htmlFor="descricao"
              className="text-[11px] uppercase tracking-[0.18em] text-sepia"
            >
              Descrição
            </Label>
            <textarea
              id="descricao"
              rows={4}
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
              className="w-full rounded-md border border-border bg-paper px-3 py-2 text-sm focus:outline-none focus:border-ferrugem focus:ring-2 focus:ring-ferrugem/20 transition resize-y"
              placeholder="Detalhes da tarefa..."
            />
          </div>

          <div className="flex items-center gap-2">
            <input
              id="vale_nota"
              type="checkbox"
              checked={valeNota}
              onChange={(e) => setValeNota(e.target.checked)}
              className="rounded border-input"
            />
            <Label htmlFor="vale_nota" className="cursor-pointer">
              Esta tarefa vale nota
            </Label>
          </div>

          {valeNota && (
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label
                  htmlFor="nota_maxima"
                  className="text-[11px] uppercase tracking-[0.18em] text-sepia"
                >
                  Nota máxima
                </Label>
                <Input
                  id="nota_maxima"
                  type="number"
                  step="0.01"
                  min="0"
                  max="99.99"
                  required
                  value={notaMaxima}
                  onChange={(e) => setNotaMaxima(e.target.value)}
                  placeholder="Ex.: 10"
                />
              </div>
              <div className="space-y-2">
                <Label
                  htmlFor="peso"
                  className="text-[11px] uppercase tracking-[0.18em] text-sepia"
                >
                  Peso (média ponderada)
                </Label>
                <Input
                  id="peso"
                  type="number"
                  step="0.1"
                  min="0"
                  max="9.99"
                  value={peso}
                  onChange={(e) => setPeso(e.target.value)}
                />
              </div>
            </div>
          )}

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
              Cancelar
            </Button>
            <Button type="submit" disabled={enviando}>
              {enviando ? "Salvando..." : "Salvar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
