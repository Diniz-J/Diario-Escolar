import { useState } from "react";

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
import { useAlunos } from "@/features/alunos/hooks";
import { useVinculosDoAluno } from "@/features/responsaveis/hooks";
import { usePermissoes } from "@/features/auth/usePermissoes";
import { useEscolas } from "@/features/escolas/hooks";
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
  // Select de escola só pra admin global — demais perfis têm escola no
  // JWT e o backend deduz (AutoEscopoEscolaSerializerMixin). Sem isso, o
  // admin (escola_id null) criava plano sem escola e o INSERT estourava
  // 500 numa coluna NOT NULL.
  const { ehAdminGlobal } = usePermissoes();
  const escolasQuery = useEscolas();

  // Estado nasce dos props — a página remonta o dialog (`key`) a cada
  // abertura, então não há `useEffect` pra resetar.
  const [alunoId, setAlunoId] = useState<string>(
    plano ? String(plano.aluno) : "",
  );
  const [pagadorId, setPagadorId] = useState<string>(
    plano?.pagador ? String(plano.pagador) : "",
  );
  // Só a escolha explícita do admin; o valor que vale é o derivado abaixo.
  const [escolaId, setEscolaId] = useState<string>("");
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

  // O pagador sai dos **vínculos deste aluno**, não da lista de
  // responsáveis da escola: o `clean()` do backend exige que o titular da
  // cobrança seja responsável do aluno, e oferecer os outros poria um
  // terceiro no boleto da família.
  //
  // Editando, o aluno é fixo e vem do plano (o select dele só aparece na
  // criação). Criando, depende do que foi escolhido agora.
  const alunoDoPagador = editando ? plano.aluno : Number(alunoId) || null;
  const vinculosQuery = useVinculosDoAluno(alunoDoPagador);

  // Aluno e escola entram na validação só na criação. Os vínculos
  // alimentam o pagador, que é opcional no contrato, então a falha
  // deles avisa sem travar.
  const falhouCarregar =
    alunosQuery.isError ||
    vinculosQuery.isError ||
    (ehAdminGlobal && escolasQuery.isError);
  const bloqueiaEnvio =
    !editando &&
    (alunosQuery.isError || (ehAdminGlobal && escolasQuery.isError));
  const vinculos = vinculosQuery.data ?? [];

  // Trocar o aluno invalida o pagador escolhido: ele é responsável do
  // anterior. Limpar no handler, e não num efeito, é o padrão da casa —
  // e aqui é também o que evita mandar um par que o backend recusaria.
  function escolherAluno(id: string) {
    setAlunoId(id);
    setPagadorId("");
  }

  // Pré-seleciona a única escola disponível (perfil comum só vê a sua).
  const escolas = escolasQuery.data;
  const escolaEfetiva =
    escolaId || (escolas?.length === 1 ? String(escolas[0].id) : "");

  async function salvar() {
    setErro(null);
    if (!editando && alunoId === "") {
      setErro("Escolha o aluno.");
      return;
    }
    if (!editando && ehAdminGlobal && !escolaEfetiva) {
      setErro("Selecione a escola.");
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
      // Vazio = contrato sem titular de cobrança, que é o caso de quem
      // recebe na secretaria. Manda `null` em vez de omitir pra que
      // limpar o campo numa edição realmente limpe.
      pagador: pagadorId ? Number(pagadorId) : null,
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
          // `escola` só pra admin global; demais perfis o backend deduz.
          ...(ehAdminGlobal && escolaEfetiva
            ? { escola: Number(escolaEfetiva) }
            : {}),
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
          {!editando && ehAdminGlobal && (
            <div className="space-y-2">
              <Label className={LABEL_CLASS}>Escola</Label>
              <Select value={escolaEfetiva} onValueChange={setEscolaId}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Escolha a escola" />
                </SelectTrigger>
                <SelectContent>
                  {(escolas ?? []).map((e) => (
                    <SelectItem key={e.id} value={String(e.id)}>
                      {e.nome}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {!editando && (
            <div className="space-y-2">
              <Label className={LABEL_CLASS}>Aluno</Label>
              <Select value={alunoId} onValueChange={escolherAluno}>
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

          {/* Só aparece quando há aluno: sem ele a lista seria vazia e o
              campo, um mistério. */}
          {alunoDoPagador != null && (
            <div className="space-y-2">
              <Label className={LABEL_CLASS}>Pagador</Label>
              {vinculos.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  {vinculosQuery.isPending
                    ? "Carregando responsáveis..."
                    : "Este aluno não tem responsável vinculado. Cadastre o vínculo em Responsáveis para poder emitir cobrança."}
                </p>
              ) : (
                <>
                  <Select value={pagadorId} onValueChange={setPagadorId}>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Sem pagador definido" />
                    </SelectTrigger>
                    <SelectContent>
                      {vinculos.map((v) => (
                        <SelectItem
                          key={v.responsavel}
                          value={String(v.responsavel)}
                        >
                          {v.responsavel_nome} ({v.responsavel_email})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-sepia">
                    Quem recebe a cobrança. Só é exigido para emitir no
                    gateway — quem recebe na secretaria pode deixar vazio.
                  </p>
                </>
              )}
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
          <Button
            type="button"
            onClick={salvar}
            disabled={enviando || bloqueiaEnvio}
          >
            {enviando ? "Salvando..." : editando ? "Salvar" : "Criar plano"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
