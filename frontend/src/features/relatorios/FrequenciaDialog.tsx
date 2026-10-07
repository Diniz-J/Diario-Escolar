import { useState, type FormEvent } from "react";

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
import { usePeriodosAvaliativos } from "@/features/periodos-avaliativos/hooks";

import {
  useBaixarRelatorioFrequencia,
  type FormatoRelatorio,
} from "./hooks";
import { SeletorFormato } from "./SeletorFormato";

interface FrequenciaDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  turmaId: number;
  turmaNome: string;
  anoLetivo: number;
}

// Valores especiais do select de recorte. Id de período é number, então
// estas duas strings não colidem.
const TUDO = "tudo";
const PERSONALIZADO = "personalizado";

// Escolhe recorte e formato do relatório de frequência da turma.
//
// O recorte oferece os períodos avaliativos do ano letivo da turma como
// atalho, porque é assim que a secretaria pensa ("frequência do 2º
// bimestre") — datas soltas ficam atrás de "Datas personalizadas".
export function FrequenciaDialog({
  open,
  onOpenChange,
  turmaId,
  turmaNome,
  anoLetivo,
}: FrequenciaDialogProps) {
  const [recorte, setRecorte] = useState<string>(TUDO);
  const [dataInicio, setDataInicio] = useState("");
  const [dataFim, setDataFim] = useState("");
  const [formato, setFormato] = useState<FormatoRelatorio>("pdf");

  const periodosQuery = usePeriodosAvaliativos({ ano_letivo: anoLetivo });
  const baixar = useBaixarRelatorioFrequencia();

  const personalizado = recorte === PERSONALIZADO;
  // Datas personalizadas sem nenhuma das duas pontas seria o mesmo que
  // "tudo" — nesse caso o botão fica travado pra não gerar um arquivo
  // que não é o que foi pedido.
  const podeBaixar =
    !personalizado || Boolean(dataInicio) || Boolean(dataFim);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!podeBaixar) return;

    const periodo =
      recorte === TUDO || personalizado ? undefined : Number(recorte);

    baixar.mutate(
      {
        turma: turmaId,
        formato,
        ...(periodo ? { periodo } : {}),
        ...(personalizado && dataInicio ? { data_inicio: dataInicio } : {}),
        ...(personalizado && dataFim ? { data_fim: dataFim } : {}),
      },
      { onSuccess: () => onOpenChange(false) },
    );
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            Relatório de frequência
          </DialogTitle>
          <DialogDescription>
            Frequência de cada aluno de {turmaNome}, com alerta de quem
            está abaixo do mínimo de 75%.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
              Recorte
            </Label>
            <Select value={recorte} onValueChange={setRecorte}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={TUDO}>Todo o período registrado</SelectItem>
                {periodosQuery.data?.map((periodo) => (
                  <SelectItem key={periodo.id} value={String(periodo.id)}>
                    {periodo.nome}
                  </SelectItem>
                ))}
                <SelectItem value={PERSONALIZADO}>
                  Datas personalizadas
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          {personalizado && (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label
                  htmlFor="freq-inicio"
                  className="text-[11px] uppercase tracking-[0.18em] text-sepia"
                >
                  De
                </Label>
                <Input
                  id="freq-inicio"
                  type="date"
                  value={dataInicio}
                  onChange={(e) => setDataInicio(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label
                  htmlFor="freq-fim"
                  className="text-[11px] uppercase tracking-[0.18em] text-sepia"
                >
                  Até
                </Label>
                <Input
                  id="freq-fim"
                  type="date"
                  value={dataFim}
                  onChange={(e) => setDataFim(e.target.value)}
                />
              </div>
            </div>
          )}

          <SeletorFormato valor={formato} onChange={setFormato} />

          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              disabled={baixar.isPending}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={baixar.isPending || !podeBaixar}
            >
              {baixar.isPending ? "Gerando..." : "Baixar"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
