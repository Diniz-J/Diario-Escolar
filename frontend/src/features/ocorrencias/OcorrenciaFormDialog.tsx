import axios from "axios";
import { useEffect, useMemo, useState, type FormEvent } from "react";

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
import { useAlunos } from "@/features/alunos/hooks";
import { useProfessores } from "@/features/professores/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import type { Ocorrencia, OcorrenciaInput, OcorrenciaStatus } from "@/types/api";

import { STATUS_OPTIONS } from "./constants";
import { useCreateOcorrencia, useUpdateOcorrencia } from "./hooks";

interface OcorrenciaFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  ocorrencia?: Ocorrencia | null;
}

const PROFESSOR_NENHUM = "__none__";

export function OcorrenciaFormDialog({
  open,
  onOpenChange,
  ocorrencia,
}: OcorrenciaFormDialogProps) {
  const turmasQuery = useTurmas();
  const alunosQuery = useAlunos();
  const professoresQuery = useProfessores();
  const createMutation = useCreateOcorrencia();
  const updateMutation = useUpdateOcorrencia();

  const editando = ocorrencia != null;
  const hoje = new Date().toISOString().slice(0, 10);

  const [turmaId, setTurmaId] = useState<string>("");
  const [alunoId, setAlunoId] = useState<string>("");
  const [professorId, setProfessorId] = useState<string>(PROFESSOR_NENHUM);
  const [status, setStatus] = useState<OcorrenciaStatus>("aberta");
  const [descricao, setDescricao] = useState("");
  const [dataOcorrencia, setDataOcorrencia] = useState(hoje);
  const [erro, setErro] = useState<string | null>(null);

  // Filtra alunos pela turma selecionada. Se nenhuma turma, lista vazia
  // — o select de aluno aparece desabilitado.
  const alunosDaTurma = useMemo(() => {
    if (!turmaId || !alunosQuery.data) return [];
    const id = parseInt(turmaId, 10);
    return alunosQuery.data.filter((a) => a.turma === id);
  }, [turmaId, alunosQuery.data]);

  useEffect(() => {
    if (open) {
      setErro(null);
      if (ocorrencia) {
        // Em edição: pré-seleciona a turma a partir do aluno da ocorrência.
        const alunoOriginal = alunosQuery.data?.find(
          (a) => a.id === ocorrencia.aluno,
        );
        setTurmaId(
          String(alunoOriginal?.turma ?? ocorrencia.turma),
        );
        setAlunoId(String(ocorrencia.aluno));
        setProfessorId(
          ocorrencia.professor != null
            ? String(ocorrencia.professor)
            : PROFESSOR_NENHUM,
        );
        setStatus(ocorrencia.status);
        setDescricao(ocorrencia.descricao);
        setDataOcorrencia(ocorrencia.data_ocorrencia);
      } else {
        setTurmaId("");
        setAlunoId("");
        setProfessorId(PROFESSOR_NENHUM);
        setStatus("aberta");
        setDescricao("");
        setDataOcorrencia(hoje);
      }
    }
  }, [open, ocorrencia, alunosQuery.data, hoje]);

  // Se o usuário troca a turma, limpa o aluno (evita inconsistência
  // visual de manter aluno de outra turma no select).
  function handleTurmaChange(novoTurmaId: string) {
    setTurmaId(novoTurmaId);
    setAlunoId("");
  }

  const enviando = createMutation.isPending || updateMutation.isPending;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro(null);

    const aluno = alunosQuery.data?.find((a) => String(a.id) === alunoId);
    if (!aluno) {
      setErro("Selecione um aluno.");
      return;
    }

    const payload: OcorrenciaInput = {
      escola: aluno.escola,
      turma: aluno.turma, // backend exige; derivamos do aluno
      aluno: aluno.id,
      professor:
        professorId !== PROFESSOR_NENHUM ? parseInt(professorId, 10) : null,
      descricao,
      data_ocorrencia: dataOcorrencia,
      status,
    };

    try {
      if (editando && ocorrencia) {
        await updateMutation.mutateAsync({
          id: ocorrencia.id,
          patch: payload,
        });
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
          <DialogTitle>
            {editando ? "Editar ocorrência" : "Nova ocorrência"}
          </DialogTitle>
          <DialogDescription>
            {editando
              ? "Atualize os dados da ocorrência."
              : "Registre uma ocorrência envolvendo um aluno."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Turma</Label>
              <Select value={turmaId} onValueChange={handleTurmaChange}>
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
              <Label>Aluno</Label>
              <Select
                value={alunoId}
                onValueChange={setAlunoId}
                disabled={!turmaId}
              >
                <SelectTrigger className="w-full">
                  <SelectValue
                    placeholder={
                      turmaId
                        ? alunosDaTurma.length === 0
                          ? "Nenhum aluno nesta turma"
                          : "Selecione um aluno"
                        : "Escolha uma turma antes"
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {alunosDaTurma.map((a) => (
                    <SelectItem key={a.id} value={String(a.id)}>
                      {a.nome_completo} ({a.matricula})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label>Professor que registrou (opcional)</Label>
            <Select value={professorId} onValueChange={setProfessorId}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Selecione" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={PROFESSOR_NENHUM}>— Nenhum —</SelectItem>
                {professoresQuery.data?.map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>
                    {p.nome_completo || `Professor #${p.id}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Status</Label>
              <Select
                value={status}
                onValueChange={(v) => setStatus(v as OcorrenciaStatus)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map((s) => (
                    <SelectItem key={s.value} value={s.value}>
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="data_ocorrencia">Data</Label>
              <Input
                id="data_ocorrencia"
                type="date"
                required
                max={hoje}
                value={dataOcorrencia}
                onChange={(e) => setDataOcorrencia(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="descricao">Descrição</Label>
            <textarea
              id="descricao"
              required
              rows={5}
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-y"
              placeholder="O que aconteceu?"
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
