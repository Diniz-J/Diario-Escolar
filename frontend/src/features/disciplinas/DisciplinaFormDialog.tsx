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
  const { user } = useAuth();
  // Auto-scope: usuário com escola no JWT não precisa selecionar;
  // backend deduz. Admin global continua escolhendo.
  const escolaAuto = user?.escola_id ?? null;
  const escolasQuery = useEscolas();
  const createMutation = useCreateDisciplina();
  const updateMutation = useUpdateDisciplina();

  const editando = disciplina != null;

  const [nome, setNome] = useState("");
  const [escolaId, setEscolaId] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setErro(null);
      if (disciplina) {
        setNome(disciplina.nome);
        setEscolaId(String(disciplina.escola));
      } else {
        setNome("");
        const escolas = escolasQuery.data;
        setEscolaId(escolas?.length === 1 ? String(escolas[0].id) : "");
      }
    }
  }, [open, disciplina, escolasQuery.data]);

  const enviando = createMutation.isPending || updateMutation.isPending;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro(null);

    if (!escolaAuto && !escolaId) {
      setErro("Selecione uma escola.");
      return;
    }

    // `ativa` é omitido: no create o backend usa default=True; no edit
    // mantém o valor atual porque o endpoint é PATCH parcial.
    // `escola` é omitido quando o usuário tem escola no perfil — backend
    // deduz via `AutoEscopoEscolaMixin`.
    const payload: DisciplinaInput = {
      ...(escolaAuto == null && escolaId
        ? { escola: parseInt(escolaId, 10) }
        : {}),
      nome,
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

  // Select de escola só pra admin global com múltiplas escolas.
  const mostrarEscolaSelect =
    escolaAuto == null && (escolasQuery.data?.length ?? 0) > 1;

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
