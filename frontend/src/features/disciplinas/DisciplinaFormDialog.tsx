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
  // Estritamente `perfil === "admin"` enxerga o select de escola e
  // envia escola no payload. Outros perfis NUNCA — backend deduz via
  // `AutoEscopoEscolaMixin`. Ver usePermissoes pro porquê desse gate
  // explícito (segurança contra usuário não-admin com escola_id=null).
  const { ehAdminGlobal } = usePermissoes();
  const escolasQuery = useEscolas();
  const createMutation = useCreateDisciplina();
  const updateMutation = useUpdateDisciplina();

  const editando = disciplina != null;

  // Estado nasce dos props — a página remonta o dialog (`key={formKey}`) a
  // cada abertura, então não há `useEffect` pra repreencher.
  const [nome, setNome] = useState(disciplina?.nome ?? "");
  // `escolaId` guarda só a escolha explícita. O valor que vale é o
  // derivado abaixo: a lista de escolas chega depois do mount, e
  // sincronizá-la com `setState` num efeito é o que a regra
  // `react-hooks/set-state-in-effect` acusa. Derivar dá o mesmo
  // resultado sem render extra — e sem o estado poder divergir da lista.
  const [escolaId, setEscolaId] = useState(
    disciplina ? String(disciplina.escola) : "",
  );
  const [erro, setErro] = useState<string | null>(null);

  const escolas = escolasQuery.data;
  const escolaEfetiva =
    escolaId || (escolas?.length === 1 ? String(escolas[0].id) : "");

  // O select de escola só existe pro admin global, e só ele manda o
  // campo — pros outros perfis o backend deduz pelo JWT. Então a falha
  // de `/escolas/` só atrapalha o admin: contar sem esse gate travaria
  // o diretor por causa de uma lista que ele não usa.
  const falhouCarregar = ehAdminGlobal && escolasQuery.isError;

  const enviando = createMutation.isPending || updateMutation.isPending;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro(null);

    if (ehAdminGlobal && !escolaEfetiva) {
      setErro("Selecione uma escola.");
      return;
    }

    // `ativa` é omitido: no create o backend usa default=True; no edit
    // mantém o valor atual porque o endpoint é PATCH parcial.
    // `escola` no payload SÓ pra admin global. Outros perfis: backend
    // deduz via `AutoEscopoEscolaMixin` a partir do JWT.
    const payload: DisciplinaInput = {
      ...(ehAdminGlobal && escolaEfetiva
        ? { escola: parseInt(escolaEfetiva, 10) }
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
    ehAdminGlobal;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
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
            <Label
              htmlFor="nome"
              className="text-[11px] uppercase tracking-[0.18em] text-sepia"
            >
              Nome
            </Label>
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
              <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                Escola
              </Label>
              <Select value={escolaEfetiva} onValueChange={setEscolaId}>
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
              disabled={enviando}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={enviando || falhouCarregar}>
              {enviando ? "Salvando..." : "Salvar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
