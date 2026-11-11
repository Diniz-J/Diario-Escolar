import { useSyncExternalStore } from "react";

// Lógica de instalação do PWA, separada do componente de UI
// (`BotaoInstalarApp`) porque o `react-refresh/only-export-components`
// exige que um arquivo de componente exporte só componentes — hook e
// helpers vivem aqui.
//
// Comportamento por plataforma:
// - Android/Chrome e desktop (Chromium): o navegador dispara
//   `beforeinstallprompt`; guardamos o evento e o botão o aciona.
// - iPhone/Safari: a Apple não expõe instalação por JS — o componente
//   mostra as instruções manuais.

// `beforeinstallprompt` não está no lib DOM padrão do TS.
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

// Captura em nível de módulo: o `beforeinstallprompt` dispara cedo (no
// load), antes de qualquer componente montar. Guardamos aqui e avisamos
// os componentes vivos pelos inscritos.
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

export function ehIOS(): boolean {
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

export interface EstadoInstalacao {
  // Há algo a oferecer: prompt nativo (Android/desktop) ou o caminho
  // manual do iOS. Falso quando já instalado ou sem suporte.
  podeInstalar: boolean;
  // Prompt nativo disponível (dispara instalação de verdade).
  temPrompt: boolean;
  iOS: boolean;
  // Dispara o prompt nativo. No iOS (sem prompt) não faz nada — a UI
  // mostra as instruções manuais.
  instalar: () => Promise<void>;
}

export function usePwaInstall(): EstadoInstalacao {
  const estado = useSyncExternalStore(subscrever, snapshot);
  const temPrompt = estado.split("|")[0] === "true";
  const instalado = estado.split("|")[1] === "true";
  const iOS = ehIOS();
  const podeInstalar = instalado ? false : temPrompt || iOS;

  async function instalar(): Promise<void> {
    if (!promptGuardado) return;
    await promptGuardado.prompt();
    await promptGuardado.userChoice;
    // O evento é de uso único: o browser o invalida após `prompt()`.
    promptGuardado = null;
    notificar();
  }

  return { podeInstalar, temPrompt, iOS, instalar };
}

// Só o booleano, pra quem envolve o botão num card poder esconder o card
// inteiro (texto incluso) quando não há instalação possível.
export function usePodeInstalar(): boolean {
  return usePwaInstall().podeInstalar;
}
