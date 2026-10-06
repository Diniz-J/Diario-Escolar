import { useMemo, useState } from "react";

import { Pagination } from "@/components/Pagination";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useAuth } from "@/features/auth/useAuth";
import { usePermissoes } from "@/features/auth/usePermissoes";
import { useDisciplinas } from "@/features/disciplinas/hooks";
import { MaterialDeleteDialog } from "@/features/materiais/MaterialDeleteDialog";
import { MaterialFormDialog } from "@/features/materiais/MaterialFormDialog";
import {
  useMateriaisPaginated,
  useReativarMaterial,
} from "@/features/materiais/hooks";
import { useProfessores } from "@/features/professores/hooks";
import { useTurmas } from "@/features/turmas/hooks";
import type { Material } from "@/types/api";

const FILTRO_TODOS = "__all__";
const PAGE_SIZE = 20;

function formatarData(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR");
}

// O backend só aceita http/https (API e admin), mas material inserido por
// shell ou importação sem `full_clean` passaria. Um `javascript:` aqui
// viraria link clicável na tela do staff — só renderiza http(s).
function linkSeguro(link: string): boolean {
  return /^https?:\/\//i.test(link);
}

// Mural de materiais — lado do staff (fatia 5b do PORTAL.md). O professor
// vê e publica só o próprio; a direção vê a escola toda, publica em nome
// de um professor e modera (despublica). O backend é a fronteira real:
// a lista já chega escopada por perfil.
export function MuralPage() {
  const { user } = useAuth();
  // Mesmo conjunto do backend (`PERFIS_PRIVILEGIADOS`): admin/diretor/
  // secretaria/coordenador.
  const { podeModificarCadastros: ehDirecao } = usePermissoes();
  const professoresQuery = useProfessores();
  const turmasQuery = useTurmas();
  const disciplinasQuery = useDisciplinas();

  const [filtroTurma, setFiltroTurma] = useState<string>(FILTRO_TODOS);
  const [filtroProfessor, setFiltroProfessor] = useState<string>(FILTRO_TODOS);
  const [mostrarDespublicados, setMostrarDespublicados] = useState(false);
  const [page, setPage] = useState(1);
  const [formAberto, setFormAberto] = useState(false);
  // Incrementa a cada abertura: remonta o dialog, que inicializa o estado
  // a partir dos props (sem `useEffect` + `setState` pra resetar).
  const [formKey, setFormKey] = useState(0);
  const [editando, setEditando] = useState<Material | null>(null);
  const [despublicando, setDespublicando] = useState<Material | null>(null);
  const reativarMutation = useReativarMaterial();

  // Filtro server-side mudou: volta pra página 1 no próprio handler —
  // senão pode cair numa página que não existe no novo subset.
  function filtrar<T>(setter: (valor: T) => void) {
    return (valor: T) => {
      setter(valor);
      setPage(1);
    };
  }

  // Professor logado: cruza o user_id do JWT com o Professor da escola
  // (mesmo critério do Diário de Aula).
  const meuProfessor = useMemo(
    () =>
      professoresQuery.data?.find((p) => p.usuario === user?.user_id) ?? null,
    [professoresQuery.data, user?.user_id],
  );

  const materiaisQuery = useMateriaisPaginated(
    {
      ativo: !mostrarDespublicados,
      ...(filtroTurma !== FILTRO_TODOS && { turma: Number(filtroTurma) }),
      ...(ehDirecao &&
        filtroProfessor !== FILTRO_TODOS && {
          professor: Number(filtroProfessor),
        }),
    },
    { page, page_size: PAGE_SIZE },
  );

  const nomeTurma = (id: number) =>
    turmasQuery.data?.find((t) => t.id === id)?.nome ?? `Turma #${id}`;
  const nomeDisciplina = (id: number) =>
    disciplinasQuery.data?.find((d) => d.id === id)?.nome ??
    `Disciplina #${id}`;

  // Inspetor (alias de professor) não tem cadastro de Professor: não publica.
  const podePublicar = ehDirecao || meuProfessor != null;
  const materiais = materiaisQuery.data?.results ?? [];
  const totalCount = materiaisQuery.data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  // Despublicar/republicar tira o item do filtro atual. Se era o único da
  // página, ela deixa de existir e o backend responde 404 (paginação do
  // DRF) — a tela mostraria erro. Volta uma página antes do refetch.
  function voltarSeEsvaziou() {
    if (materiais.length === 1 && page > 1) setPage((p) => p - 1);
  }

  function abrirForm(material: Material | null) {
    setEditando(material);
    setFormKey((k) => k + 1);
    setFormAberto(true);
  }

  return (
    <div className="p-4 md:p-8 space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <h1 className="font-heading text-[28px] md:text-[34px] tracking-tight text-tinta leading-[1.15]">
            Mural
          </h1>
          <div className="h-px w-10 bg-ferrugem" />
          <p className="text-sm text-muted-foreground max-w-xl">
            Materiais da turma — lista de exercícios, leitura, recado com
            link. Aparecem no portal para os responsáveis dos alunos.
          </p>
        </div>
        {podePublicar && (
          <Button onClick={() => abrirForm(null)}>Publicar material</Button>
        )}
      </header>

      <MaterialFormDialog
        key={formKey}
        open={formAberto}
        onOpenChange={setFormAberto}
        material={editando}
        ehDirecao={ehDirecao}
        meuProfessor={meuProfessor}
      />
      <MaterialDeleteDialog
        material={despublicando}
        onOpenChange={(aberto) => !aberto && setDespublicando(null)}
        onDespublicado={voltarSeEsvaziou}
      />

      <div className="flex flex-wrap gap-3 items-end">
        <Select value={filtroTurma} onValueChange={filtrar(setFiltroTurma)}>
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={FILTRO_TODOS}>Todas as turmas</SelectItem>
            {(turmasQuery.data ?? []).map((t) => (
              <SelectItem key={t.id} value={String(t.id)}>
                {t.nome}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {ehDirecao && (
          <Select
            value={filtroProfessor}
            onValueChange={filtrar(setFiltroProfessor)}
          >
            <SelectTrigger className="w-56">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={FILTRO_TODOS}>Todos os professores</SelectItem>
              {(professoresQuery.data ?? []).map((p) => (
                <SelectItem key={p.id} value={String(p.id)}>
                  {p.nome_completo}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        <div className="flex items-center gap-2">
          <Switch
            id="mostrar-despublicados"
            checked={mostrarDespublicados}
            onCheckedChange={filtrar(setMostrarDespublicados)}
          />
          <Label
            htmlFor="mostrar-despublicados"
            className="text-[11px] uppercase tracking-[0.18em] text-sepia cursor-pointer select-none"
          >
            Mostrar despublicados
          </Label>
        </div>
      </div>

      {materiaisQuery.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : materiaisQuery.isError ? (
        <p className="text-sm text-destructive">
          Não foi possível carregar o mural.
        </p>
      ) : materiais.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {/* Sem cadastro de professor (ex.: inspetor) a lista é sempre
              vazia — "nenhum publicado ainda" daria a entender que um dia
              vai ter. Mesmo tom do aviso do Diário de Aula. */}
          {!podePublicar && !professoresQuery.isLoading
            ? "Esta área é de quem leciona — seu usuário não tem um cadastro de professor vinculado."
            : mostrarDespublicados
              ? "Nenhum material despublicado."
              : "Nenhum material publicado ainda."}
        </p>
      ) : (
        <>
          <div className="rounded-lg border border-border overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Título</TableHead>
                  <TableHead className="hidden md:table-cell">
                    Turma — disciplina
                  </TableHead>
                  {ehDirecao && (
                    <TableHead className="hidden lg:table-cell">
                      Professor
                    </TableHead>
                  )}
                  <TableHead className="hidden sm:table-cell">
                    Publicado
                  </TableHead>
                  <TableHead className="text-right">Ações</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {materiais.map((m) => (
                  <TableRow key={m.id}>
                    <TableCell>
                      <span className="font-medium inline-flex items-center gap-2">
                        {m.titulo}
                        {!m.ativo && (
                          <span className="text-[10px] uppercase tracking-wide bg-muted text-muted-foreground px-1.5 py-0.5 rounded">
                            despublicado
                          </span>
                        )}
                      </span>
                      {/* Abaixo de md a coluna de turma some; sem isto o
                          professor de várias turmas não sabe de qual é. */}
                      <span className="block text-xs text-muted-foreground md:hidden">
                        {nomeTurma(m.turma)} — {nomeDisciplina(m.disciplina)}
                      </span>
                      {linkSeguro(m.link) && (
                        <a
                          href={m.link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="block text-xs text-ferrugem underline underline-offset-2 truncate max-w-xs"
                        >
                          abrir link
                        </a>
                      )}
                    </TableCell>
                    <TableCell className="hidden md:table-cell text-muted-foreground">
                      {nomeTurma(m.turma)} — {nomeDisciplina(m.disciplina)}
                    </TableCell>
                    {ehDirecao && (
                      <TableCell className="hidden lg:table-cell text-muted-foreground">
                        {m.professor_nome}
                      </TableCell>
                    )}
                    <TableCell className="hidden sm:table-cell text-muted-foreground text-sm">
                      {formatarData(m.publicado_em)}
                    </TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon-sm">
                            ⋯
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => abrirForm(m)}>
                            Editar
                          </DropdownMenuItem>
                          {m.ativo ? (
                            <DropdownMenuItem
                              onClick={() => setDespublicando(m)}
                              className="text-destructive focus:text-destructive"
                            >
                              Despublicar
                            </DropdownMenuItem>
                          ) : (
                            <DropdownMenuItem
                              onClick={() =>
                                reativarMutation.mutate(m.id, {
                                  onSuccess: voltarSeEsvaziou,
                                })
                              }
                              disabled={reativarMutation.isPending}
                            >
                              Publicar de novo
                            </DropdownMenuItem>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <Pagination
            page={page}
            totalPages={totalPages}
            onPageChange={setPage}
            totalLabel={`${totalCount} ${totalCount === 1 ? "material" : "materiais"} no total`}
          />
        </>
      )}
    </div>
  );
}
