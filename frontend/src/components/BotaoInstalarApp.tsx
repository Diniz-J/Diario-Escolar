import { useState, useSyncExternalStore } from "react";
import { Download, Share } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

// Botão "Instalar app" (PWA). O comportamento muda por plataforma:
//
// - Android/Chrome e desktop (Chrome/Edge): o navegador dispara o evento
//   `beforeinstallprompt`. Guardamos o evento e o botão o aciona —
//   instalação nativa de verdade.
// - iPhone/Safari: a Apple NÃO expõe instalação por JS. O botão abre um
//   diálogo com o passo a passo (Compartilhar → Adicionar à Tela de Início).
// - Já instalado (display-mode standalone), ou navegador sem suporte e
//   não-iOS (ex.: Firefox/Safari desktop): o componente não renderiza nada.

// `beforeinstallprompt` não está no lib DOM padrão do TS.
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

// Captura em nível de módulo: o `beforeinstallprompt` dispara cedo (no
// load), antes de qualquer componente montar. Guardamos aqui e avisamos
// os componentes vivos pelos inscritos — assim o botão funciona mesmo
// montando depois do evento.
let promptGuardado: BeforeInstallPromptEvent | null = null;
const inscritos = new Set<() => void>();

function notificar(): void {
  for (const fn of inscritos) fn();
}

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (e) => {
    // Impede o mini-infobar automático do Chrome: a instalação passa a
    // ser só pelo nosso botão.
    e.preventDefault();
    promptGuardado = e as BeforeInstallPromptEvent;
    notificar();
  });
  window.addEventListener("appinstalled", () => {
    promptGuardado = null;
    notificar();
  });
}

function ehIOS(): boolean {
  if (typeof navigator === "undefined") return false;
  return /iphone|ipad|ipod/i.test(navigator.userAgent);
}

function jaInstalado(): boolean {
  if (typeof window === "undefined") return false;
  const standalone = window.matchMedia?.("(display-mode: standalone)").matches;
  // iOS marca o app instalado via `navigator.standalone`.
  const iosStandalone =
    (navigator as unknown as { standalone?: boolean }).standalone === true;
  return Boolean(standalone || iosStandalone);
}

function subscrever(callback: () => void): () => void {
  inscritos.add(callback);
  return () => {
    inscritos.delete(callback);
  };
}

// Snapshot como string estável (primitivo), pra não quebrar o
// `useSyncExternalStore` com objeto novo a cada render.
function snapshot(): string {
  return `${promptGuardado !== null}|${jaInstalado()}`;
}

// Diz se há algo a oferecer: ou o prompt nativo (Android/desktop) ou o
// caminho manual do iOS. Exposto pra quem envolve o botão num card poder
// esconder o card inteiro (texto incluso) quando não há instalação possível.
export function usePodeInstalar(): boolean {
  const estado = useSyncExternalStore(subscrever, snapshot);
  const temPrompt = estado.split("|")[0] === "true";
  const instalado = estado.split("|")[1] === "true";
  if (instalado) return false;
  return temPrompt || ehIOS();
}

interface BotaoInstalarAppProps {
  variant?: React.ComponentProps<typeof Button>["variant"];
  size?: React.ComponentProps<typeof Button>["size"];
  className?: string;
}

export function BotaoInstalarApp({
  variant = "outline",
  size = "default",
  className,
}: BotaoInstalarAppProps) {
  const estado = useSyncExternalStore(subscrever, snapshot);
  const temPrompt = estado.split("|")[0] === "true";
  const instalado = estado.split("|")[1] === "true";
  const [modalIOS, setModalIOS] = useState(false);

  const iOS = ehIOS();

  // Já instalado: não há o que oferecer.
  if (instalado) return null;
  // Sem prompt nativo e fora do iOS (ex.: Firefox/Safari desktop): o botão
  // não teria o que fazer, então nem aparece.
  if (!temPrompt && !iOS) return null;

  async function instalar(): Promise<void> {
    // iOS sem prompt nativo: só dá pra ensinar o caminho manual.
    if (iOS && !temPrompt) {
      setModalIOS(true);
      return;
    }
    if (!promptGuardado) return;
    await promptGuardado.prompt();
    await promptGuardado.userChoice;
    // O evento é de uso único: o browser o invalida após `prompt()`.
    promptGuardado = null;
    notificar();
  }

  return (
    <>
      <Button
        type="button"
        variant={variant}
        size={size}
        className={className}
        onClick={instalar}
      >
        {iOS && !temPrompt ? <Share /> : <Download />}
        Instalar app
      </Button>

      <Dialog open={modalIOS} onOpenChange={setModalIOS}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="font-heading">Instalar no iPhone</DialogTitle>
            <DialogDescription>
              O Safari instala o app pela própria barra — siga os passos:
            </DialogDescription>
          </DialogHeader>
          <ol className="text-sm text-muted-foreground space-y-2 list-decimal pl-5">
            <li>
              Toque no ícone <strong>Compartilhar</strong> (o quadrado com a
              seta para cima), na barra do Safari.
            </li>
            <li>
              Role e toque em <strong>"Adicionar à Tela de Início"</strong>.
            </li>
            <li>
              Confirme em <strong>"Adicionar"</strong>. O Diário aparece como
              app na tela inicial.
            </li>
          </ol>
        </DialogContent>
      </Dialog>
    </>
  );
}
