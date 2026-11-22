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
import { useEscolas } from "@/features/escolas/hooks";
import type { TempoAula, TempoAulaInput, Turno } from "@/types/api";

import { TURNOS, horaCurta } from "./constants";
import { useCreateTempoAula, useUpdateTempoAula } from "./hooks";

const LABEL = "text-[11px] uppercase tracking-[0.18em] text-sepia";

interface TempoAulaFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tempo?: TempoAula | null;
  // Turno pré-selecionado quando a tela já está filtrada por um.
  turnoInicial?: Turno | "";
}

export function TempoAulaFormDialog({
  open,
  onOpenChange,
  tempo,
  turnoInicial = "",
}: TempoAulaFormDialogProps) {
  const { ehAdminGlobal } = usePermissoes();
  const escolasQuery = useEscolas();
  const createMutation = useCreateTempoAula();
  const updateMutation = useUpdateTempoAula();

  const editando = tempo != null;

  // Estado nasce dos props — a página remonta o dialog (`key={formKey}`).
  const [turno, setTurno] = useState<Turno | "">(tempo?.turno ?? turnoInicial);
  const [ordem, setOrdem] = useState(String(tempo?.ordem ?? ""));
  const [horaInicio, setHoraInicio] = useState(horaCurta(tempo?.hora_inicio));
  const [horaFim, setHoraFim] = useState(horaCurta(tempo?.hora_fim));
  const [escolaId, setEscolaId] = useState(tempo ? String(tempo.escola) : "");
  const [erro, setErro] = useState<string | null>(null);

  const escolas = escolasQuery.data;
  const escolaEfetiva =
    escolaId || (escolas?.length === 1 ? String(escolas[0].id) : "");
  // Só o admin global vê e envia `escola`; pros outros o backend deduz do
  // JWT, então a falha de `/escolas/` não pode travá-los.
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
    const ordemNum = parseInt(ordem, 10);
    if (!Number.isInteger(ordemNum) || ordemNum < 1) {
      setErro("A ordem do tempo começa em 1.");
      return;
    }

    const payload: TempoAulaInput = {
      ...(ehAdminGlobal && escolaEfetiva
        ? { escola: parseInt(escolaEfetiva, 10) }
        : {}),
      turno,
      ordem: ordemNum,
      hora_inicio: horaInicio,
      hora_fim: horaFim,
    };

    try {
      if (editando && tempo) {
        await updateMutation.mutateAsync({ id: tempo.id, patch: payload });
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
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            {editando ? "Editar tempo" : "Novo tempo de aula"}
          </DialogTitle>
          <DialogDescription>
            O horário de um tempo do turno. É o catálogo que a grade das
            turmas usa.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className={LABEL}>Turno</Label>
              <Select value={turno} onValueChange={(v) => setTurno(v as Turno)}>
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
              <Label htmlFor="ordem" className={LABEL}>
                Ordem
              </Label>
              <Input
                id="ordem"
                type="number"
                required
                min={1}
                value={ordem}
                onChange={(e) => setOrdem(e.target.value)}
                placeholder="1"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="hora_inicio" className={LABEL}>
                Início
              </Label>
              <Input
                id="hora_inicio"
                type="time"
                required
                value={horaInicio}
                onChange={(e) => setHoraInicio(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="hora_fim" className={LABEL}>
                Fim
              </Label>
              <Input
                id="hora_fim"
                type="time"
                required
                value={horaFim}
                onChange={(e) => setHoraFim(e.target.value)}
              />
            </div>
          </div>

          {ehAdminGlobal && (
            <div className="space-y-2">
              <Label className={LABEL}>Escola</Label>
              <Select value={escolaEfetiva} onValueChange={setEscolaId}>
                <SelectTrigger>
                  <SelectValue placeholder="Selecione uma escola" />
                </SelectTrigger>
                <SelectContent>
                  {escolas?.map((e) => (
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
