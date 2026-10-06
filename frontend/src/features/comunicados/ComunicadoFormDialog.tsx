import axios from "axios";
import { useEffect, useMemo, useState, type FormEvent } from "react";

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
import { useTurmas } from "@/features/turmas/hooks";
import type {
  Comunicado,
  ComunicadoDestino,
  ComunicadoInput,
} from "@/types/api";

import { DESTINO_OPTIONS } from "./constants";
import { useCreateComunicado, useUpdateComunicado } from "./hooks";

interface ComunicadoFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  comunicado?: Comunicado | null;
}

/**
 * Formulário de rascunho do comunicado.
 *
 * Importante: este diálogo **nunca envia email**. Salvar cria/atualiza um
 * rascunho; o disparo é um passo separado e confirmado
 * (`EnviarComunicadoDialog`). O texto da UI reforça isso porque a
 * expectativa natural de quem clica "Salvar" num formulário de
 * comunicado é que algo já saiu.
 */
export function ComunicadoFormDialog({
  open,
  onOpenChange,
  comunicado,
}: ComunicadoFormDialogProps) {
  // `escola` no payload SÓ pra admin global; demais perfis o backend
  // deduz do JWT (AutoEscopoEscolaMixin).
  const { ehAdminGlobal } = usePermissoes();
  const escolasQuery = useEscolas();
  const turmasQuery = useTurmas();
  const createMutation = useCreateComunicado();
  const updateMutation = useUpdateComunicado();

  const editando = comunicado != null;

  const [titulo, setTitulo] = useState("");
  const [mensagem, setMensagem] = useState("");
  const [destino, setDestino] = useState<ComunicadoDestino>("escola");
  const [turmasSelecionadas, setTurmasSelecionadas] = useState<number[]>([]);
  const [escolaId, setEscolaId] = useState<string>("");
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setErro(null);
    if (comunicado) {
      setTitulo(comunicado.titulo);
      setMensagem(comunicado.mensagem);
      setDestino(comunicado.destino);
      setTurmasSelecionadas(comunicado.turmas);
      setEscolaId(String(comunicado.escola));
    } else {
      setTitulo("");
      setMensagem("");
      setDestino("escola");
      setTurmasSelecionadas([]);
      setEscolaId("");
    }
  }, [open, comunicado]);

  // Admin global opera em várias escolas: as turmas ofertadas têm que ser
  // as da escola escolhida, senão ele monta um comunicado que o backend
  // recusa ("turmas devem pertencer à mesma escola").
  const turmasDisponiveis = useMemo(() => {
    const todas = turmasQuery.data ?? [];
    if (!ehAdminGlobal) return todas;
    if (!escolaId) return [];
    const id = parseInt(escolaId, 10);
    return todas.filter((t) => t.escola === id);
  }, [turmasQuery.data, ehAdminGlobal, escolaId]);

  function alternarTurma(id: number) {
    setTurmasSelecionadas((atuais) =>
      atuais.includes(id)
        ? atuais.filter((t) => t !== id)
        : [...atuais, id],
    );
  }

  // Trocar de escola invalida as turmas já marcadas (são de outra escola).
  function handleEscolaChange(valor: string) {
    setEscolaId(valor);
    setTurmasSelecionadas([]);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setErro(null);

    if (!titulo.trim()) {
      setErro("Informe um título.");
      return;
    }
    if (!mensagem.trim()) {
      setErro("Escreva a mensagem do comunicado.");
      return;
    }
    if (ehAdminGlobal && !escolaId) {
      setErro("Selecione uma escola.");
      return;
    }
    if (destino === "turmas" && turmasSelecionadas.length === 0) {
      setErro("Selecione ao menos uma turma.");
      return;
    }

    const payload: ComunicadoInput = {
      ...(ehAdminGlobal && escolaId
        ? { escola: parseInt(escolaId, 10) }
        : {}),
      titulo: titulo.trim(),
      mensagem: mensagem.trim(),
      destino,
      // Em "toda a escola" o backend normaliza pra lista vazia; mandamos
      // vazio já daqui pra não gravar um estado contraditório.
      turmas: destino === "turmas" ? turmasSelecionadas : [],
    };

    try {
      if (editando && comunicado) {
        await updateMutation.mutateAsync({ id: comunicado.id, patch: payload });
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

  const salvando = createMutation.isPending || updateMutation.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-heading tracking-tight">
            {editando ? "Editar rascunho" : "Novo comunicado"}
          </DialogTitle>
          <DialogDescription>
            O comunicado é salvo como rascunho. Nenhum email é enviado até
            você usar o botão "Enviar" e confirmar.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {ehAdminGlobal && (
            <div className="space-y-2">
              <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                Escola
              </Label>
              <Select value={escolaId} onValueChange={handleEscolaChange}>
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

          <div className="space-y-2">
            <Label
              htmlFor="titulo"
              className="text-[11px] uppercase tracking-[0.18em] text-sepia"
            >
              Título
            </Label>
            <Input
              id="titulo"
              required
              maxLength={200}
              value={titulo}
              onChange={(e) => setTitulo(e.target.value)}
              placeholder="Ex.: Reunião de pais — 20/10"
            />
            <p className="text-xs text-muted-foreground">
              Vai no assunto do email que os responsáveis recebem.
            </p>
          </div>

          <div className="space-y-2">
            <Label
              htmlFor="mensagem"
              className="text-[11px] uppercase tracking-[0.18em] text-sepia"
            >
              Mensagem
            </Label>
            <textarea
              id="mensagem"
              required
              rows={8}
              value={mensagem}
              onChange={(e) => setMensagem(e.target.value)}
              className="w-full rounded-md border border-border bg-paper px-3 py-2 text-sm focus:outline-none focus:border-ferrugem focus:ring-2 focus:ring-ferrugem/20 transition resize-y"
              placeholder="Escreva o comunicado como você quer que os responsáveis leiam."
            />
            <p className="text-xs text-muted-foreground">
              As quebras de linha são preservadas no email.
            </p>
          </div>

          <div className="space-y-2">
            <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
              Destinatários
            </Label>
            <Select
              value={destino}
              onValueChange={(v) => setDestino(v as ComunicadoDestino)}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DESTINO_OPTIONS.map((d) => (
                  <SelectItem key={d.value} value={d.value}>
                    {d.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Só responsáveis de alunos ativos recebem o comunicado.
            </p>
          </div>

          {destino === "turmas" && (
            <div className="space-y-2">
              <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
                Turmas
              </Label>
              {turmasDisponiveis.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  {ehAdminGlobal && !escolaId
                    ? "Selecione uma escola antes."
                    : "Nenhuma turma cadastrada."}
                </p>
              ) : (
                <div className="max-h-48 overflow-y-auto rounded-md border border-border p-3 space-y-2">
                  {turmasDisponiveis.map((t) => (
                    <div key={t.id} className="flex items-center gap-2">
                      <input
                        id={`turma-${t.id}`}
                        type="checkbox"
                        checked={turmasSelecionadas.includes(t.id)}
                        onChange={() => alternarTurma(t.id)}
                        className="rounded border-input"
                      />
                      <Label
                        htmlFor={`turma-${t.id}`}
                        className="cursor-pointer font-normal"
                      >
                        {t.nome} — {t.turno_display} {t.ano_letivo}
                      </Label>
                    </div>
                  ))}
                </div>
              )}
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
              disabled={salvando}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={salvando}>
              {salvando ? "Salvando..." : "Salvar rascunho"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
