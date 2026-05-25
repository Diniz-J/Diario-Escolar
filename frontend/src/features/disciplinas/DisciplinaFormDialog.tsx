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
import { useEscolas } from "@/features/escolas/hooks";
import type { Disciplina, DisciplinaInput } from "@/types/api";

import { useCreateDisciplina, useUpdateDisciplina } from "./hooks";

interface DisciplinaFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  disciplina?: Disciplina | null;
}

export function DisciplinaFormDialog({
  open,
  onOpenChange,
  disciplina,
}: DisciplinaFormDialogProps) {
  const escolasQuery = useEscolas();
  const createMutation = useCreateDisciplina();
  const updateMutation = useUpdateDisciplina();

  const editando = disciplina != null;

  const [nome, setNome] = useState("");
  const [escolaId, setEscolaId] = useState("");
  const [ativa, setAtiva] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setErro(null);
      if (disciplina) {
        setNome(disciplina.nome);
        setEscolaId(String(disciplina.escola));
        setAtiva(disciplina.ativa);
      } else {
        setNome("");
        const escolas = escolasQuery.data;
        setEscolaId(escolas?.length === 1 ? String(escolas[0].id) : "");
        setAtiva(true);
      }
    }
  }, [open, disciplina, escolasQuery.data]);

  const enviando = createMutation.isPending || updateMutation.isPending;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro(null);

    if (!escolaId) {
      setErro("Selecione uma escola.");
      return;
    }

    const payload: DisciplinaInput = {
      escola: parseInt(escolaId, 10),
      nome,
      ativa,
    };

    try {
      if (editando && disciplina) {
        await updateMutation.mutateAsync({ id: disciplina.id, patch: payload });
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

  // Mostra select de escola só quando há mais de uma (admin), seguindo
  // o padrão do form de Turma.
  const mostrarEscolaSelect = (escolasQuery.data?.length ?? 0) > 1;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {editando ? "Editar disciplina" : "Nova disciplina"}
          </DialogTitle>
          <DialogDescription>
            {editando
              ? "Atualize os dados da disciplina."
              : "Cadastre uma matéria oferecida pela escola."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="nome">Nome</Label>
            <Input
              id="nome"
              required
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              placeholder="Ex.: Matemática"
            />
          </div>

          {mostrarEscolaSelect && (
            <div className="space-y-2">
              <Label>Escola</Label>
              <Select value={escolaId} onValueChange={setEscolaId}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Selecione uma escola" />
                </SelectTrigger>
                <SelectContent>
                  {escolasQuery.data?.map((e) => (
                    <SelectItem key={e.id} value={String(e.id)}>
                      {e.nome}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="flex items-center gap-2">
            <input
              id="ativa"
              type="checkbox"
              checked={ativa}
              onChange={(e) => setAtiva(e.target.checked)}
              className="rounded border-input"
            />
            <Label htmlFor="ativa" className="cursor-pointer">
              Disciplina ativa
            </Label>
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
