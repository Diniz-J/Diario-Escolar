import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useAlunos } from "@/features/alunos/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import type { ResponsavelStaff } from "@/types/api";

import {
  useCriarVinculo,
  useRemoverVinculo,
  useVinculosDoResponsavel,
} from "./hooks";

interface VinculosDialogProps {
  responsavel: ResponsavelStaff | null;
  onOpenChange: (open: boolean) => void;
}

/**
 * Vínculos de um responsável — adicionar e remover filhos.
 *
 * É a tela que fecha a fatia 4 do `RESPONSAVEIS.md`: sem ela o vínculo só
 * nasce no `/admin/`, e a capacidade de ter mãe e pai cadastrados, que o
 * envio de email já sustenta, fica inalcançável pra secretaria.
 *
 * O select de alunos chama `useAlunos()` **sem filtro de `ativo`**: aluno
 * desativado mantém o histórico pro responsável (`PORTAL.md`), então
 * vincular a um filho transferido é caso legítimo. A linha marca
 * `[ inativo ]` pra não confundir.
 */
export function VinculosDialog({
  responsavel,
  onOpenChange,
}: VinculosDialogProps) {
  const [alunoId, setAlunoId] = useState<string>("");
  const vinculosQuery = useVinculosDoResponsavel(responsavel?.id ?? null);
  const alunosQuery = useAlunos();
  // `Aluno` só traz o id da turma; o nome vem daqui. Nome de aluno
  // repete numa escola, então a turma é o que desambigua no select.
  const turmasQuery = useTurmas();
  const criar = useCriarVinculo();
  const remover = useRemoverVinculo();

  const vinculos = useMemo(
    () => vinculosQuery.data ?? [],
    [vinculosQuery.data],
  );

  const nomeDaTurma = useMemo(() => {
    const mapa = new Map<number, string>();
    for (const t of turmasQuery.data ?? []) mapa.set(t.id, t.nome);
    return mapa;
  }, [turmasQuery.data]);

  // Quem já está vinculado sai do select: o backend recusaria pelo unique
  // (400) e oferecer a opção seria prometer o que não acontece.
  const disponiveis = useMemo(() => {
    const vinculados = new Set(vinculos.map((v) => v.aluno));
    return (alunosQuery.data ?? []).filter((a) => !vinculados.has(a.id));
  }, [alunosQuery.data, vinculos]);

  async function adicionar() {
    if (!responsavel || !alunoId) return;
    try {
      await criar.mutateAsync({
        responsavel: responsavel.id,
        aluno: Number(alunoId),
      });
      setAlunoId("");
    } catch (err) {
      // Toast com a mensagem do backend vem do hook.
      console.error(err);
    }
  }

  return (
    <Dialog
      open={responsavel != null}
      onOpenChange={(aberto) => {
        if (!aberto) setAlunoId("");
        onOpenChange(aberto);
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-heading">Vínculos</DialogTitle>
          <DialogDescription asChild>
            <div className="space-y-1">
              <span className="block text-foreground">
                {responsavel?.nome || "(sem nome)"}
              </span>
              <span className="block break-all">{responsavel?.email}</span>
            </div>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <div className="text-[11px] uppercase tracking-[0.18em] text-sepia">
              Filhos vinculados
            </div>
            {vinculosQuery.isLoading ? (
              <Skeleton className="h-10 w-full" />
            ) : vinculosQuery.isError ? (
              <p className="text-sm text-destructive">
                Não foi possível carregar os vínculos.
              </p>
            ) : vinculos.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Nenhum vínculo. Sem vínculo, o email deste aluno sai pelo
                campo de responsável do cadastro dele.
              </p>
            ) : (
              <ul className="divide-y divide-border rounded-md border border-border">
                {vinculos.map((v) => (
                  <li
                    key={v.id}
                    className="flex items-center justify-between gap-3 px-3 py-2"
                  >
                    <span className="text-sm">
                      {v.aluno_nome}
                      {v.aluno_turma ? (
                        <span className="text-muted-foreground">
                          {" "}
                          · {v.aluno_turma}
                        </span>
                      ) : null}
                      {!v.aluno_ativo ? (
                        <span className="text-muted-foreground">
                          {" "}
                          [ inativo ]
                        </span>
                      ) : null}
                    </span>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-destructive hover:text-destructive"
                      disabled={remover.isPending}
                      onClick={() => remover.mutate(v.id)}
                    >
                      Remover
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="space-y-2">
            <div className="text-[11px] uppercase tracking-[0.18em] text-sepia">
              Vincular aluno
            </div>
            <div className="flex gap-2">
              <Select value={alunoId} onValueChange={setAlunoId}>
                <SelectTrigger className="flex-1">
                  <SelectValue placeholder="Escolha um aluno..." />
                </SelectTrigger>
                <SelectContent>
                  {disponiveis.map((a) => (
                    <SelectItem key={a.id} value={String(a.id)}>
                      {a.nome_completo}
                      {nomeDaTurma.has(a.turma)
                        ? ` · ${nomeDaTurma.get(a.turma)}`
                        : ""}
                      {!a.ativo ? " [ inativo ]" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                onClick={adicionar}
                disabled={!alunoId || criar.isPending}
              >
                {criar.isPending ? "Vinculando..." : "Vincular"}
              </Button>
            </div>
            {disponiveis.length === 0 && !alunosQuery.isLoading && (
              <p className="text-xs text-muted-foreground">
                Todos os alunos da escola já estão vinculados a este
                responsável.
              </p>
            )}
          </div>

          {/* A consequência que não é óbvia: remover o último vínculo NÃO
              silencia o aluno. Pelo RESPONSAVEIS.md §4.1, aluno com zero
              vínculos volta a receber pelo campo de texto do cadastro.
              Sem este aviso a secretaria acha que removeu e silenciou. */}
          <p className="text-xs text-muted-foreground border-t border-border pt-3">
            Remover um vínculo tira o acesso deste responsável ao portal
            daquele aluno. Se for o último vínculo do aluno, o email volta a
            sair pelo campo de responsável do cadastro dele — o aluno não
            fica sem notificação.
          </p>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Fechar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
