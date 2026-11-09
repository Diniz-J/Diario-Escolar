"use client"

import { Toaster as Sonner, type ToasterProps } from "sonner"
import { CircleCheckIcon, InfoIcon, TriangleAlertIcon, OctagonXIcon, Loader2Icon } from "lucide-react"

// `theme` fixo em "light": o app é light-mode permanente (`index.css`
// tem `color-scheme: light` e o bloco `.dark` foi removido). O wrapper do
// shadcn vinha com `theme="system"`, que faz o sonner ler
// `prefers-color-scheme` e marcar `data-sonner-theme="dark"` no aparelho
// com tema escuro. O `style` inline abaixo cobre só `--normal-*`, então
// não alcança as variáveis de `richColors` — e como todo toast do projeto
// é `success` ou `error`, o celular no escuro recebia caixa quase preta
// (`--success-bg: hsl(150, 100%, 6%)`) com texto verde-néon, dentro de
// uma tela linho. Medido no Chromium: `rgb(0, 31, 15)` contra os
// `rgb(236, 253, 243)` do tema claro.
const Toaster = ({ ...props }: ToasterProps) => {
  return (
    <Sonner
      theme="light"
      className="toaster group"
      icons={{
        success: (
          <CircleCheckIcon className="size-4" />
        ),
        info: (
          <InfoIcon className="size-4" />
        ),
        warning: (
          <TriangleAlertIcon className="size-4" />
        ),
        error: (
          <OctagonXIcon className="size-4" />
        ),
        loading: (
          <Loader2Icon className="size-4 animate-spin" />
        ),
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--border-radius": "var(--radius)",
        } as React.CSSProperties
      }
      toastOptions={{
        classNames: {
          toast: "cn-toast",
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
