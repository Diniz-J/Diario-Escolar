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
import { useAlunos } from "@/features/alunos/hooks";
import type { DescontoTipo, PlanoCobranca } from "@/types/api";

import { DESCONTO_TIPOS } from "./constants";
import { mensagemDeErro } from "./erros";
import { useCreatePlanoCobranca, useUpdatePlanoCobranca } from "./hooks";

interface PlanoCobrancaFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  // Presente = edição. O aluno fica fixo: trocar o aluno de um contrato
  // mudaria de quem são as faturas já emitidas.
  plano?: PlanoCobranca | null;
}

const LABEL_CLASS = "text-[11px] uppercase tracking-[0.18em] text-sepia";

export function PlanoCobrancaFormDialog({
  open,
  onOpenChange,
  plano,
}: PlanoCobrancaFormDialogProps) {
  const editando = plano != null;
  const createMutation = useCreatePlanoCobranca();
  const updateMutation = useUpdatePlanoCobranca();
  // Só alunos ativos: contrato novo pra aluno desativado não faz sentido.
  const alunosQuery = useAlunos({ ativo: true });

  // Estado nasce dos props — a página remonta o dialog (`key`) a cada
  // abertura, então não há `useEffect` pra resetar.
  const [alunoId, setAlunoId] = useState<string>(
    plano ? String(plano.aluno) : "",
  );
  const [valor, setValor] = useState(plano?.valor_mensalidade ?? "");
  const [diaVencimento, setDiaVencimento] = useState(
    String(plano?.dia_vencimento ?? 10),
  );
  const [descontoTipo, setDescontoTipo] = useState<DescontoTipo>(
    plano?.desconto_tipo ?? "nenhum",
  );
  const [descontoValor, setDescontoValor] = useState(
    plano?.desconto_valor ?? "0.00",
  );
  const [multa, setMulta] = useState(plano?.multa_percentual ?? "");
  const [juros, setJuros] = useState(plano?.juros_mes_percentual ?? "");
  const [vigenciaInicio, setVigenciaInicio] = useState(
    plano?.vigencia_inicio ?? "",
  );
  const [vigenciaFim, setVigenciaFim] = useState(plano?.vigencia_fim ?? "");
  const [erro, setErro] = useState<string | null>(null);

  const enviando = createMutation.isPending || updateMutation.isPending;

  async function salvar() {
    setErro(null);
    if (!editando && alunoId === "") {
      setErro("Escolha o aluno.");
      return;
    }
    if (!valor.trim()) {
      setErro("Informe o valor da mensalidade.");
      return;
    }
    if (!vigenciaInicio) {
      setErro("Informe o início da vigência.");
      return;
    }

    // `desconto_valor` tem dois significados conforme o tipo, e o backend
    // recusa valor sem tipo. Mandar zero quando é "sem desconto" evita o
    // 400 por um campo que a UI já esconde.
    const payload = {
      valor_mensalidade: valor.trim(),
      dia_vencimento: Number(diaVencimento),
      desconto_tipo: descontoTipo,
      desconto_valor:
        descontoTipo === "nenhum" ? "0.00" : descontoValor.trim() || "0.00",
      vigencia_inicio: vigenciaInicio,
      // Vazio = vigência aberta (contrato corrente, sem término).
      vigencia_fim: vigenciaFim || null,
      // Vazio = deixa o backend aplicar o default de settings.
      ...(multa.trim() && { multa_percentual: multa.trim() }),
      ...(juros.trim() && { juros_mes_percentual: juros.trim() }),
    };

    try {
      if (editando && plano) {
        await updateMutation.mutateAsync({ id: plano.id, patch: payload });
      } else {
        await createMutation.mutateAsync({
          ...payload,
          aluno: Number(alunoId),
        });
      }
      onOpenChange(false);
    } catch (err) {
      // A mensagem do backend é o que importa aqui: vigência sobreposta,
      // desconto maior que a mensalidade, aluno de outra escola.
      setErro(mensagemDeErro(err, "Não foi possível salvar o plano."));
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            {editando ? "Editar plano de cobrança" : "Novo plano de cobrança"}
          </DialogTitle>
          <DialogDescription>
            {editando && plano
              ? `${plano.aluno_nome} — contrato financeiro`
              : "O contrato que gera as faturas mensais do aluno."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          {!editando && (
            <div className="space-y-2">
              <Label className={LABEL_CLASS}>Aluno</Label>
              <Select value={alunoId} onValueChange={setAlunoId}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Escolha o aluno" />
                </SelectTrigger>
                <SelectContent>
                  {(alunosQuery.data ?? []).map((a) => (
                    <SelectItem key={a.id} value={String(a.id)}>
                      {a.nome_completo} ({a.matricula})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="plano-valor" className={LABEL_CLASS}>
                Mensalidade (R$)
              </Label>
              <Input
                id="plano-valor"
                inputMode="decimal"
                value={valor}
                onChange={(e) => setValor(e.target.value)}
                placeholder="1000.00"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="plano-dia" className={LABEL_CLASS}>
                Dia do vencimento
              </Label>
              <Input
                id="plano-dia"
                type="number"
                min={1}
                max={31}
                value={diaVencimento}
                onChange={(e) => setDiaVencimento(e.target.value)}
              />
              <p className="text-xs text-sepia">
                Em mês mais curto, usa o último dia disponível.
              </p>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label className={LABEL_CLASS}>Desconto</Label>
              <Select
                value={descontoTipo}
                onValueChange={(v) => setDescontoTipo(v as DescontoTipo)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DESCONTO_TIPOS.map((d) => (
                    <SelectItem key={d.value} value={d.value}>
                      {d.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {descontoTipo !== "nenhum" && (
              <div className="space-y-2">
                <Label htmlFor="plano-desconto" className={LABEL_CLASS}>
                  {descontoTipo === "percentual"
                    ? "Desconto (%)"
                    : "Desconto (R$)"}
                </Label>
                <Input
                  id="plano-desconto"
                  inputMode="decimal"
                  value={descontoValor}
                  onChange={(e) => setDescontoValor(e.target.value)}
                  placeholder={descontoTipo === "percentual" ? "10.00" : "150.00"}
                />
              </div>
            )}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="plano-inicio" className={LABEL_CLASS}>
                Início da vigência
              </Label>
              <Input
                id="plano-inicio"
                type="date"
                value={vigenciaInicio}
                onChange={(e) => setVigenciaInicio(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="plano-fim" className={LABEL_CLASS}>
                Fim da vigência (opcional)
              </Label>
              <Input
                id="plano-fim"
                type="date"
                value={vigenciaFim ?? ""}
                onChange={(e) => setVigenciaFim(e.target.value)}
              />
              <p className="text-xs text-sepia">
                Vazio = contrato corrente, sem data de término.
              </p>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="plano-multa" className={LABEL_CLASS}>
                Multa por atraso (%)
              </Label>
              <Input
                id="plano-multa"
                inputMode="decimal"
                value={multa}
                onChange={(e) => setMulta(e.target.value)}
                placeholder="2.00"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="plano-juros" className={LABEL_CLASS}>
                Juros ao mês (%)
              </Label>
              <Input
                id="plano-juros"
                inputMode="decimal"
                value={juros}
                onChange={(e) => setJuros(e.target.value)}
                placeholder="1.00"
              />
            </div>
          </div>
          <p className="text-xs text-sepia">
            Multa e juros ficam gravados neste contrato: mudar o padrão da
            escola depois não altera os planos já cadastrados. Em branco,
            usa o padrão.
          </p>
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
            {enviando ? "Salvando..." : editando ? "Salvar" : "Criar plano"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
