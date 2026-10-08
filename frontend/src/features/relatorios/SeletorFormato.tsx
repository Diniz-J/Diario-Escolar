import { Label } from "@/components/ui/label";

import type { FormatoRelatorio } from "./hooks";

const FORMATOS: { valor: FormatoRelatorio; label: string; nota: string }[] = [
  { valor: "pdf", label: "PDF", nota: "pra imprimir e assinar" },
  { valor: "xlsx", label: "Excel", nota: "pra continuar a conta" },
  { valor: "csv", label: "CSV", nota: "pra outro sistema" },
];

interface SeletorFormatoProps {
  valor: FormatoRelatorio;
  onChange: (formato: FormatoRelatorio) => void;
}

// Escolha de formato, compartilhada pelos diálogos de relatório.
//
// Cada opção carrega pra que serve, não só a extensão: quem trabalha na
// secretaria sabe se quer imprimir ou continuar a conta, não
// necessariamente se isso é PDF ou XLSX.
export function SeletorFormato({ valor, onChange }: SeletorFormatoProps) {
  return (
    <div className="space-y-2">
      <Label className="text-[11px] uppercase tracking-[0.18em] text-sepia">
        Formato
      </Label>
      <div className="grid grid-cols-3 gap-2">
        {FORMATOS.map((opcao) => (
          <button
            key={opcao.valor}
            type="button"
            onClick={() => onChange(opcao.valor)}
            className={`rounded-md border px-2 py-2 text-left transition-colors ${
              valor === opcao.valor
                ? "border-ferrugem bg-ferrugem/10"
                : "border-border hover:bg-muted"
            }`}
          >
            <span className="block text-sm font-medium text-tinta">
              {opcao.label}
            </span>
            <span className="block text-[10px] text-sepia/80">
              {opcao.nota}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
