import axios from "axios";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useDisciplinas } from "@/features/disciplinas/hooks";
import { PlanoEnsinoDeleteDialog } from "@/features/planos-ensino/PlanoEnsinoDeleteDialog";
import {
  usePlanoEnsino,
  useUpdatePlanoEnsino,
} from "@/features/planos-ensino/hooks";
import { useTurmas } from "@/features/turmas/hooks";

// Detalhe do plano: cabeçalho com identificação (read-only) + formulário
// longo dividido em três seções (Programação / Execução / Metadados).
// Os campos textuais são todos opcionais — o usuário preenche aos poucos.
// "Salvar" envia PATCH com todos os campos editáveis; "Desfazer" reseta
// o estado local pro último dado do servidor.
export function PlanoEnsinoDetalhePage() {
  const params = useParams<{ id: string }>();
  const navigate = useNavigate();
  const id = params.id ? parseInt(params.id, 10) : undefined;

  const planoQuery = usePlanoEnsino(id);
  const turmasQuery = useTurmas();
  const disciplinasQuery = useDisciplinas();
  const updateMutation = useUpdatePlanoEnsino();

  const [deleteAlvo, setDeleteAlvo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // Estado local dos campos editáveis. Hidratado quando a query carrega
  // e quando a mutação refeta — `useEffect` faz o sync.
  const [form, setForm] = useState({
    ementa: "",
    conteudo_programatico: "",
    objetivos_gerais: "",
    objetivos_especificos: "",
    habilidades_bncc: "",
    carga_horaria: "" as string | number,
    metodologia: "",
    recursos: "",
    avaliacao: "",
    ativo: true,
  });

  useEffect(() => {
    if (planoQuery.data) {
      setForm({
        ementa: planoQuery.data.ementa,
        conteudo_programatico: planoQuery.data.conteudo_programatico,
        objetivos_gerais: planoQuery.data.objetivos_gerais,
        objetivos_especificos: planoQuery.data.objetivos_especificos,
        habilidades_bncc: planoQuery.data.habilidades_bncc,
        carga_horaria: planoQuery.data.carga_horaria ?? "",
        metodologia: planoQuery.data.metodologia,
        recursos: planoQuery.data.recursos,
        avaliacao: planoQuery.data.avaliacao,
        ativo: planoQuery.data.ativo,
      });
    }
  }, [planoQuery.data]);

  const plano = planoQuery.data;
  const turma = plano
    ? turmasQuery.data?.find((t) => t.id === plano.turma)
    : undefined;
  const disciplina = plano
    ? disciplinasQuery.data?.find((d) => d.id === plano.disciplina)
    : undefined;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!plano) return;
    setErro(null);

    const cargaNum =
      form.carga_horaria === ""
        ? null
        : Number.isFinite(Number(form.carga_horaria))
          ? Number(form.carga_horaria)
          : null;

    try {
      await updateMutation.mutateAsync({
        id: plano.id,
        patch: {
          ementa: form.ementa,
          conteudo_programatico: form.conteudo_programatico,
          objetivos_gerais: form.objetivos_gerais,
          objetivos_especificos: form.objetivos_especificos,
          habilidades_bncc: form.habilidades_bncc,
          carga_horaria: cargaNum,
          metodologia: form.metodologia,
          recursos: form.recursos,
          avaliacao: form.avaliacao,
          ativo: form.ativo,
        },
      });
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

  return (
    <div className="p-4 md:p-8 space-y-6 max-w-4xl mx-auto">
      <header className="space-y-2">
        <Button asChild variant="ghost" size="sm" className="-ml-2">
          <Link to="/planos-ensino">← Voltar</Link>
        </Button>
        <div className="flex items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-semibold">Plano de ensino</h1>
            {plano && (
              <p className="text-sm text-muted-foreground mt-1">
                {turma?.nome ?? `Turma #${plano.turma}`} ·{" "}
                {disciplina?.nome ?? `Disciplina #${plano.disciplina}`} ·{" "}
                {plano.ano_letivo}
              </p>
            )}
          </div>
          {plano && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="icon">
                  ⋯
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  onClick={() => setDeleteAlvo(true)}
                  className="text-destructive focus:text-destructive"
                >
                  Excluir
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </header>

      {planoQuery.isLoading ? (
        <Card>
          <CardContent className="pt-6">
            <Skeleton className="h-64 w-full" />
          </CardContent>
        </Card>
      ) : planoQuery.isError || !plano ? (
        <Card>
          <CardContent className="pt-6 text-destructive">
            Plano não encontrado.
          </CardContent>
        </Card>
      ) : (
        <>
          <form onSubmit={handleSubmit} className="space-y-6">
            <Secao titulo="Programação">
              <Campo
                id="ementa"
                label="Ementa"
                value={form.ementa}
                onChange={(v) => setForm({ ...form, ementa: v })}
                rows={3}
                placeholder="Visão geral da disciplina no ano."
              />
              <Campo
                id="conteudo_programatico"
                label="Conteúdo programático"
                value={form.conteudo_programatico}
                onChange={(v) =>
                  setForm({ ...form, conteudo_programatico: v })
                }
                rows={6}
                placeholder="Lista ordenada dos temas, um por linha."
              />
              <Campo
                id="objetivos_gerais"
                label="Objetivos gerais"
                value={form.objetivos_gerais}
                onChange={(v) => setForm({ ...form, objetivos_gerais: v })}
                rows={3}
              />
              <Campo
                id="objetivos_especificos"
                label="Objetivos específicos"
                value={form.objetivos_especificos}
                onChange={(v) =>
                  setForm({ ...form, objetivos_especificos: v })
                }
                rows={4}
              />
              <Campo
                id="habilidades_bncc"
                label="Habilidades BNCC"
                value={form.habilidades_bncc}
                onChange={(v) => setForm({ ...form, habilidades_bncc: v })}
                rows={3}
                placeholder="Códigos da BNCC, um por linha (ex.: EF06MA01)."
              />
              <div className="space-y-2">
                <Label htmlFor="carga_horaria">Carga horária (horas)</Label>
                <Input
                  id="carga_horaria"
                  type="number"
                  min={0}
                  value={form.carga_horaria}
                  onChange={(e) =>
                    setForm({ ...form, carga_horaria: e.target.value })
                  }
                  className="max-w-[200px]"
                />
              </div>
            </Secao>

            <Secao titulo="Execução">
              <Campo
                id="metodologia"
                label="Metodologia"
                value={form.metodologia}
                onChange={(v) => setForm({ ...form, metodologia: v })}
                rows={4}
              />
              <Campo
                id="recursos"
                label="Recursos"
                value={form.recursos}
                onChange={(v) => setForm({ ...form, recursos: v })}
                rows={3}
                placeholder="Livros, materiais, plataformas."
              />
              <Campo
                id="avaliacao"
                label="Avaliação"
                value={form.avaliacao}
                onChange={(v) => setForm({ ...form, avaliacao: v })}
                rows={3}
                placeholder="Critérios e instrumentos avaliativos."
              />
            </Secao>

            <Card>
              <CardHeader>
                <CardTitle>Situação</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2">
                  <input
                    id="ativo"
                    type="checkbox"
                    checked={form.ativo}
                    onChange={(e) =>
                      setForm({ ...form, ativo: e.target.checked })
                    }
                    className="rounded border-input"
                  />
                  <Label htmlFor="ativo" className="cursor-pointer">
                    Plano ativo
                  </Label>
                </div>
              </CardContent>
            </Card>

            {erro && (
              <Alert variant="destructive">
                <AlertDescription>{erro}</AlertDescription>
              </Alert>
            )}

            <div className="flex justify-end gap-3 sticky bottom-4 bg-background/80 backdrop-blur p-3 rounded-md">
              <Button type="submit" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? "Salvando..." : "Salvar alterações"}
              </Button>
            </div>
          </form>

          <PlanoEnsinoDeleteDialog
            plano={deleteAlvo ? plano : null}
            onOpenChange={(open) => !open && setDeleteAlvo(false)}
            onDeleted={() => navigate("/planos-ensino")}
          />
        </>
      )}
    </div>
  );
}

function Secao({
  titulo,
  children,
}: {
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{titulo}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  );
}

function Campo({
  id,
  label,
  value,
  onChange,
  rows,
  placeholder,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  rows: number;
  placeholder?: string;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <textarea
        id={id}
        rows={rows}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-y"
      />
    </div>
  );
}
