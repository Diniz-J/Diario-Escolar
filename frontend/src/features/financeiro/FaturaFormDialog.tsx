import { useState } from "react";

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
import type { Fatura } from "@/types/api";

import { competenciaDoMes, formatarCompetencia } from "./constants";
import { mensagemDeErro } from "./erros";
import { useCreateFatura, usePlanosAtivos, useUpdateFatura } from "./hooks";

interface FaturaFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  // Presente = edição. Só valor e vencimento mudam: plano e competência
  // definem a identidade da fatura (o unique é por aluno e competência).
  fatura?: Fatura | null;
}

const LABEL_CLASS = "text-[11px] uppercase tracking-[0.18em] text-sepia";

function mesCorrente(): string {
  const agora = new Date();
  return `${agora.getFullYear()}-${String(agora.getMonth() + 1).padStart(2, "0")}`;
}

// Sugestão de vencimento a partir do dia do plano, travando no último dia
// quando o mês é curto. Só conveniência de formulário: a régua que vale é
// a da geração mensal, no backend. O usuário pode trocar a data.
function vencimentoSugerido(mes: string, dia: number): string {
  const [ano, mesNum] = mes.split("-").map(Number);
  const ultimoDia = new Date(ano, mesNum, 0).getDate();
  const escolhido = String(Math.min(dia, ultimoDia)).padStart(2, "0");
  return `${mes}-${escolhido}`;
}

// Fatura avulsa. A via normal é o `financeiro_gerar_faturas` no cron; isto
// cobre o mês em que o cron ainda não rodou (ou não está configurado) e a
// cobrança extra fora do ciclo.
export function FaturaFormDialog({
  open,
  onOpenChange,
  fatura,
}: FaturaFormDialogProps) {
  const editando = fatura != null;
  const createMutation = useCreateFatura();
  const updateMutation = useUpdateFatura();
  const planosQuery = usePlanosAtivos(!editando);

  const [planoId, setPlanoId] = useState<string>(
    fatura ? String(fatura.plano) : "",
  );
  const [mes, setMes] = useState<string>(
    fatura ? fatura.competencia.slice(0, 7) : mesCorrente(),
  );
  const [valor, setValor] = useState(fatura?.valor ?? "");
  const [vencimento, setVencimento] = useState(fatura?.vencimento ?? "");
  const [erro, setErro] = useState<string | null>(null);

  const planos = planosQuery.data ?? [];
  const enviando = createMutation.isPending || updateMutation.isPending;

  // Escolher o plano preenche valor e vencimento — o que a geração mensal
  // faria. Campos editáveis depois: a fatura avulsa pode ter outro valor.
  function escolherPlano(id: string) {
    setPlanoId(id);
    const plano = planos.find((p) => String(p.id) === id);
    if (!plano) return;
    setValor(plano.valor_efetivo);
    setVencimento(vencimentoSugerido(mes, plano.dia_vencimento));
  }

  function escolherMes(novoMes: string) {
    setMes(novoMes);
    const plano = planos.find((p) => String(p.id) === planoId);
    if (plano && novoMes) {
      setVencimento(vencimentoSugerido(novoMes, plano.dia_vencimento));
    }
  }

  async function salvar() {
    setErro(null);
    if (!editando && planoId === "") {
      setErro("Escolha o plano de cobrança.");
      return;
    }
    if (!valor.trim() || !vencimento) {
      setErro("Informe valor e vencimento.");
      return;
    }
    try {
      if (editando && fatura) {
        await updateMutation.mutateAsync({
          id: fatura.id,
          patch: { valor: valor.trim(), vencimento },
        });
      } else {
        await createMutation.mutateAsync({
          plano: Number(planoId),
          competencia: competenciaDoMes(mes),
          valor: valor.trim(),
          vencimento,
        });
      }
      onOpenChange(false);
    } catch (err) {
      // Mensagem do backend: competência repetida pro mesmo aluno é a mais
      // provável, e ela diz exatamente qual aluno e qual mês.
      setErro(mensagemDeErro(err, "Não foi possível salvar a fatura."));
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            {editando ? "Editar fatura" : "Nova fatura"}
          </DialogTitle>
          <DialogDescription>
            {editando && fatura
              ? `${fatura.aluno_nome} — competência ${formatarCompetencia(fatura.competencia)}`
              : "Cada aluno tem uma fatura por mês. O normal é a geração automática criar; esta é a avulsa."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {!editando && (
            <>
              <div className="space-y-2">
                <Label className={LABEL_CLASS}>Plano de cobrança</Label>
                <Select value={planoId} onValueChange={escolherPlano}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Escolha o aluno" />
                  </SelectTrigger>
                  <SelectContent>
                    {planos.map((p) => (
                      <SelectItem key={p.id} value={String(p.id)}>
                        {p.aluno_nome}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {!planosQuery.isLoading && planos.length === 0 && (
                  <p className="text-xs text-sepia">
                    Nenhum plano ativo. Cadastre o contrato do aluno na aba
                    Planos de cobrança.
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="fatura-mes" className={LABEL_CLASS}>
                  Competência
                </Label>
                <Input
                  id="fatura-mes"
                  type="month"
                  value={mes}
                  onChange={(e) => escolherMes(e.target.value)}
                />
              </div>
            </>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="fatura-valor" className={LABEL_CLASS}>
                Valor (R$)
              </Label>
              <Input
                id="fatura-valor"
                inputMode="decimal"
                value={valor}
                onChange={(e) => setValor(e.target.value)}
                placeholder="1000.00"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="fatura-vencimento" className={LABEL_CLASS}>
                Vencimento
              </Label>
              <Input
                id="fatura-vencimento"
                type="date"
                value={vencimento}
                onChange={(e) => setVencimento(e.target.value)}
              />
            </div>
          </div>
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
            disabled={enviando}
          >
            Cancelar
          </Button>
          <Button type="button" onClick={salvar} disabled={enviando}>
            {enviando ? "Salvando..." : editando ? "Salvar" : "Criar fatura"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
