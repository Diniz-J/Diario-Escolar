import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import type { Comunicado } from "@/types/api";

import { useComunicadoPrevia, useEnviarComunicado } from "./hooks";

interface EnviarComunicadoDialogProps {
  comunicado: Comunicado | null;
  onOpenChange: (open: boolean) => void;
  onEnviado?: () => void;
}

function plural(n: number, singular: string, plural_: string) {
  return n === 1 ? singular : plural_;
}

/**
 * Confirmação do disparo — o ponto sem volta da feature.
 *
 * Email não tem "desfazer", então o diálogo mostra o alcance real ANTES
 * de enviar: quantos responsáveis, quantas mensagens após a dedup de
 * irmãos e quantos alunos estão sem email cadastrado. A contagem vem do
 * endpoint `previa/`, que lê o cadastro no momento em que o diálogo abre.
 *
 * O botão fica desabilitado enquanto a prévia carrega: confirmar um envio
 * sem ver o número derrota o propósito da tela.
 */
export function EnviarComunicadoDialog({
  comunicado,
  onOpenChange,
  onEnviado,
}: EnviarComunicadoDialogProps) {
  const aberto = comunicado != null;
  const previaQuery = useComunicadoPrevia(comunicado?.id, {
    enabled: aberto,
  });
  const enviarMutation = useEnviarComunicado();

  async function handleConfirm() {
    if (!comunicado) return;
    try {
      await enviarMutation.mutateAsync(comunicado.id);
      onOpenChange(false);
      onEnviado?.();
    } catch (err) {
      // O toast de erro (incluindo o caso 409) vem do hook.
      console.error(err);
    }
  }

  const previa = previaQuery.data;
  const semPublico = previa != null && previa.total_emails === 0;

  return (
    <AlertDialog open={aberto} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Enviar este comunicado?</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3">
              <p>
                O comunicado{" "}
                <strong className="text-foreground">
                  {comunicado?.titulo}
                </strong>{" "}
                será enviado por email aos responsáveis. Esta ação não pode
                ser desfeita.
              </p>

              {previaQuery.isLoading && <Skeleton className="h-16 w-full" />}

              {previaQuery.isError && (
                <p className="text-destructive">
                  Não foi possível calcular o alcance do comunicado. Tente
                  novamente.
                </p>
              )}

              {previa && (
                <div className="rounded-md bg-muted p-3 space-y-1 text-sm">
                  <div>
                    <strong className="text-foreground">
                      {previa.total_emails}
                    </strong>{" "}
                    {plural(previa.total_emails, "email", "emails")} para{" "}
                    <strong className="text-foreground">
                      {previa.total_alunos}
                    </strong>{" "}
                    {plural(previa.total_alunos, "aluno", "alunos")}.
                  </div>
                  {previa.total_alunos > previa.total_emails &&
                    previa.total_emails > 0 && (
                      <div className="text-muted-foreground">
                        Responsáveis com mais de um filho recebem uma única
                        mensagem.
                      </div>
                    )}
                  {previa.total_emails > previa.total_alunos && (
                    <div className="text-muted-foreground">
                      Alunos com mais de um responsável geram uma mensagem
                      para cada.
                    </div>
                  )}
                  {previa.total_sem_email > 0 && (
                    <div className="text-destructive">
                      {previa.total_sem_email}{" "}
                      {plural(previa.total_sem_email, "aluno", "alunos")} sem
                      email de responsável cadastrado{" "}
                      {plural(previa.total_sem_email, "ficará", "ficarão")} de
                      fora.
                    </div>
                  )}
                </div>
              )}

              {semPublico && (
                <p className="text-destructive">
                  Nenhum responsável tem email cadastrado — não há para quem
                  enviar.
                </p>
              )}
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={enviarMutation.isPending}>
            Cancelar
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={handleConfirm}
            disabled={
              enviarMutation.isPending ||
              previaQuery.isLoading ||
              previaQuery.isError ||
              semPublico
            }
          >
            {enviarMutation.isPending
              ? "Enviando..."
              : previa
                ? `Enviar ${previa.total_emails} ${plural(previa.total_emails, "email", "emails")}`
                : "Enviar"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
