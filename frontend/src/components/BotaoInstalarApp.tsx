import { useState } from "react";
import { Download, Share } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { dispensarInstalacao, usePwaInstall } from "@/lib/pwa";

// Botão "Instalar app" (PWA). A lógica de plataforma mora em `@/lib/pwa`;
// aqui é só a UI:
// - Android/desktop: aciona o prompt nativo de instalação.
// - iPhone/Safari: abre um diálogo com o passo a passo manual.
// - Já instalado ou sem suporte: não renderiza nada.

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
  const { podeInstalar, temPrompt, iOS, instalar } = usePwaInstall();
  const [modalIOS, setModalIOS] = useState(false);

  if (!podeInstalar) return null;

  async function aoClicar(): Promise<void> {
    // iOS sem prompt nativo: só dá pra ensinar o caminho manual.
    if (iOS && !temPrompt) {
      setModalIOS(true);
      return;
    }
    await instalar();
  }

  return (
    <>
      <Button
        type="button"
        variant={variant}
        size={size}
        className={className}
        onClick={aoClicar}
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
          {/* Saída manual do convite. No iPhone a aba do Safari não tem
              como saber que o app já foi adicionado à tela de início
              (`navigator.standalone` só é verdadeiro dentro do app), e
              sem isto o convite voltaria a cada visita pelo navegador.
              Dispensar desmonta o componente inteiro — daí não precisar
              fechar o diálogo antes. */}
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={dispensarInstalacao}
            >
              Já instalei, não mostrar de novo
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
