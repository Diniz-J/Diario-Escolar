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
import { usePermissoes } from "@/features/auth/usePermissoes";
import { useEscolas } from "@/features/escolas/hooks";
import type {
  PeriodoAvaliativo,
  PeriodoAvaliativoInput,
} from "@/types/api";

import {
  useCreatePeriodoAvaliativo,
  useUpdatePeriodoAvaliativo,
} from "./hooks";

interface PeriodoAvaliativoFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  periodo?: PeriodoAvaliativo | null;
  // Quando a página tem um filtro de ano ativo, herdamos como default
  // pra abrir o form já com o ano correto preenchido.
  anoLetivoDefault?: number;
}

// Fallback razoável quando não há período cadastrado nem filtro ativo.
const ANO_ATUAL = new Date().getFullYear();

export function PeriodoAvaliativoFormDialog({
  open,
  onOpenChange,
  periodo,
  anoLetivoDefault,
}: PeriodoAvaliativoFormDialogProps) {
  // Select de escola **só** pra `perfil === "admin"`. Outros perfis
  // nunca veem nem mandam — ver usePermissoes pra o porquê.
  const { ehAdminGlobal } = usePermissoes();
  const escolasQuery = useEscolas();
  const createMutation = useCreatePeriodoAvaliativo();
  const updateMutation = useUpdatePeriodoAvaliativo();

  const editando = periodo != null;

  const [nome, setNome] = useState("");
  const [ordem, setOrdem] = useState("");
  const [anoLetivo, setAnoLetivo] = useState("");
  const [dataInicio, setDataInicio] = useState("");
  const [dataFim, setDataFim] = useState("");
  const [escolaId, setEscolaId] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setErro(null);
    if (periodo) {
      setNome(periodo.nome);
      setOrdem(String(periodo.ordem));
      setAnoLetivo(String(periodo.ano_letivo));
      setDataInicio(periodo.data_inicio);
      setDataFim(periodo.data_fim);
      setEscolaId(String(periodo.escola));
    } else {
      setNome("");
      setOrdem("");
      setAnoLetivo(String(anoLetivoDefault ?? ANO_ATUAL));
      setDataInicio("");
      setDataFim("");
      const escolas = escolasQuery.data;
      setEscolaId(escolas?.length === 1 ? String(escolas[0].id) : "");
    }
  }, [open, periodo, anoLetivoDefault, escolasQuery.data]);

  const enviando = createMutation.isPending || updateMutation.isPending;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErro(null);

    if (ehAdminGlobal && !escolaId) {
      setErro("Selecione uma escola.");
      return;
    }

    const ordemNum = parseInt(ordem, 10);
    const anoNum = parseInt(anoLetivo, 10);
    if (Number.isNaN(ordemNum) || ordemNum < 1) {
      setErro("Ordem precisa ser um número inteiro a partir de 1.");
      return;
    }
    if (Number.isNaN(anoNum)) {
      setErro("Ano letivo inválido.");
      return;
    }
    if (dataInicio >= dataFim) {
      setErro("A data de fim precisa ser posterior à data de início.");
      return;
    }

    const payload: PeriodoAvaliativoInput = {
      ...(ehAdminGlobal && escolaId
        ? { escola: parseInt(escolaId, 10) }
        : {}),
      nome,
      ordem: ordemNum,
      ano_letivo: anoNum,
      data_inicio: dataInicio,
      data_fim: dataFim,
    };

    try {
      if (editando && periodo) {
        await updateMutation.mutateAsync({ id: periodo.id, patch: payload });
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

  const mostrarEscolaSelect =
    ehAdminGlobal;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            {editando ? "Editar período" : "Novo período avaliativo"}
          </DialogTitle>
          <DialogDescription>
            {editando
              ? "Atualize nome, ordem ou intervalo do período."
              : "Bimestre, trimestre ou semestre da escola. Sem cálculo automático — a escola decide a régua."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="md:col-span-2 space-y-2">
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
                placeholder="Ex.: 1º Bimestre"
              />
            </div>
            <div className="space-y-2">
              <Label
                htmlFor="ordem"
                className="text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Ordem
              </Label>
              <Input
                id="ordem"
                required
                type="number"
                min={1}
                value={ordem}
                onChange={(e) => setOrdem(e.target.value)}
                placeholder="1"
              />
            </div>
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
              required
              type="number"
              value={anoLetivo}
              onChange={(e) => setAnoLetivo(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label
                htmlFor="data_inicio"
                className="text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Data início
              </Label>
              <Input
                id="data_inicio"
                required
                type="date"
                value={dataInicio}
                onChange={(e) => setDataInicio(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label
                htmlFor="data_fim"
                className="text-[11px] uppercase tracking-[0.18em] text-sepia"
              >
                Data fim
              </Label>
              <Input
                id="data_fim"
                required
                type="date"
                value={dataFim}
                onChange={(e) => setDataFim(e.target.value)}
              />
            </div>
          </div>

          {mostrarEscolaSelect && (
            <div className="space-y-2">
              <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                Escola
              </Label>
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
