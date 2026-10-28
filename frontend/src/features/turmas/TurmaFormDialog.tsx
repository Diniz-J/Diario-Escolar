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
import type { Turma, TurmaInput, Turno } from "@/types/api";

import { useCreateTurma, useUpdateTurma } from "./hooks";

interface TurmaFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  turma?: Turma | null;
}

const TURNOS: { value: Turno; label: string }[] = [
  { value: "matutino", label: "Matutino" },
  { value: "vespertino", label: "Vespertino" },
  { value: "noturno", label: "Noturno" },
  { value: "integral", label: "Integral" },
];

export function TurmaFormDialog({
  open,
  onOpenChange,
  turma,
}: TurmaFormDialogProps) {
  // Select de escola **só** pra `perfil === "admin"`. Diretor/secretaria/
  // professor/inspetor nunca veem nem enviam — backend deduz a escola
  // do JWT via `AutoEscopoEscolaMixin`. Gate estrito por perfil pra
  // garantir que usuário não-admin sem `escola_id` (cenário de borda)
  // jamais veja a UI de seleção.
  const { ehAdminGlobal } = usePermissoes();
  const escolasQuery = useEscolas();
  const createMutation = useCreateTurma();
  const updateMutation = useUpdateTurma();

  const editando = turma != null;

  // Estado nasce dos props — a página remonta o dialog (`key={formKey}`) a
  // cada abertura, então não há `useEffect` pra repreencher.
  const [nome, setNome] = useState(turma?.nome ?? "");
  const [turno, setTurno] = useState<Turno | "">(turma?.turno ?? "");
  const [anoLetivo, setAnoLetivo] = useState<string>(
    String(turma?.ano_letivo ?? new Date().getFullYear()),
  );
  // `escolaId` guarda só a escolha explícita; o valor que vale é o
  // derivado abaixo. A lista de escolas chega depois do mount, e
  // sincronizá-la com `setState` num efeito é o que a regra
  // `react-hooks/set-state-in-effect` acusa.
  const [escolaId, setEscolaId] = useState<string>(
    turma ? String(turma.escola) : "",
  );
  const [ativa, setAtiva] = useState(turma?.ativa ?? true);
  const [erro, setErro] = useState<string | null>(null);

  // Pré-seleciona a única escola disponível (usuário comum só vê a sua,
  // via EscopoEscolaMixin do backend).
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

    if (!turno) {
      setErro("Selecione um turno.");
      return;
    }
    if (ehAdminGlobal && !escolaEfetiva) {
      setErro("Selecione uma escola.");
      return;
    }
    const anoNum = parseInt(anoLetivo, 10);
    if (!Number.isInteger(anoNum) || anoNum < 1900 || anoNum > 2100) {
      setErro("Informe um ano letivo válido.");
      return;
    }

    const payload: TurmaInput = {
      // `escola` SÓ pra admin global. Demais perfis: backend deduz
      // via JWT (AutoEscopoEscolaMixin). Mesmo defensivo: se outro
      // perfil tiver `escolaId` no estado por algum bug, NÃO envia.
      ...(ehAdminGlobal && escolaEfetiva
        ? { escola: parseInt(escolaEfetiva, 10) }
        : {}),
      nome,
      turno,
      ano_letivo: anoNum,
      ativa,
    };

    try {
      if (editando && turma) {
        await updateMutation.mutateAsync({ id: turma.id, patch: payload });
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

  // Mostra select de escola SÓ se o usuário não tem escola no perfil
  // (admin global) E há mais de uma escola disponível. Pra qualquer
  // outro perfil, o backend resolve automaticamente.
  const mostrarEscolaSelect =
    ehAdminGlobal;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            {editando ? "Editar turma" : "Nova turma"}
          </DialogTitle>
          <DialogDescription>
            {editando
              ? "Atualize os dados da turma."
              : "Preencha os dados para cadastrar uma turma."}
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
              placeholder="Ex.: 1º Ano A"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                Turno
              </Label>
              <Select
                value={turno}
                onValueChange={(v) => setTurno(v as Turno)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Selecione" />
                </SelectTrigger>
                <SelectContent>
                  {TURNOS.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label
                htmlFor="ano_letivo"
                className="text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Ano letivo
              </Label>
              <Input
                id="ano_letivo"
                type="number"
                required
                min={1900}
                max={2100}
                value={anoLetivo}
                onChange={(e) => setAnoLetivo(e.target.value)}
              />
            </div>
          </div>

          {mostrarEscolaSelect && (
            <div className="space-y-2">
              <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                Escola
              </Label>
              <Select value={escolaEfetiva} onValueChange={setEscolaId}>
                <SelectTrigger>
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
              Turma ativa
            </Label>
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
