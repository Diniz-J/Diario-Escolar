import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { UsuariosPage } from "@/pages/UsuariosPage";
import { autenticarComo } from "@/test/autenticar";
import { renderizar } from "@/test/render";
import { servidor } from "@/test/servidor";

const API = "http://api.test/api/v1";

function usuario(extra: Record<string, unknown> = {}) {
  return {
    id: 1,
    username: "ana.sec",
    email: "ana@escola.test",
    first_name: "Ana",
    last_name: "Lima",
    perfil: "secretaria",
    escola: 1,
    is_active: true,
    senha_definida: true,
    ...extra,
  };
}

function responder(usuarios: unknown[], professores: unknown[] = []) {
  servidor.use(
    http.get(`${API}/usuarios/`, () => HttpResponse.json(usuarios)),
    http.get(`${API}/professores/`, () => HttpResponse.json(professores)),
    // O dialog carrega escolas pro select que só o admin global vê. O
    // hook não é condicional, então a requisição sai pra qualquer
    // perfil — e sem handler o afterEach do setup reprova.
    http.get(`${API}/escolas/`, () =>
      HttpResponse.json([{ id: 1, nome: "Escola Teste" }]),
    ),
  );
}

describe("UsuariosPage", () => {
  it("lista os usuários com o perfil", async () => {
    autenticarComo("diretor");
    responder([usuario(), usuario({ id: 2, username: "bia", perfil: "professor", first_name: "Bia", last_name: "Souza" })]);
    renderizar(<UsuariosPage />);

    expect(await screen.findByText("Ana Lima")).toBeInTheDocument();
    expect(screen.getByText("Secretaria")).toBeInTheDocument();
    expect(screen.getByText("Bia Souza")).toBeInTheDocument();
    expect(screen.getByText("Professor")).toBeInTheDocument();
  });

  it("esconde inativos até o toggle, e aí mostra só eles", async () => {
    autenticarComo("diretor");
    responder([
      usuario(),
      usuario({ id: 2, username: "saiu", first_name: "Carlos", last_name: "Dias", is_active: false }),
    ]);
    renderizar(<UsuariosPage />);

    expect(await screen.findByText("Ana Lima")).toBeInTheDocument();
    expect(screen.queryByText("Carlos Dias")).not.toBeInTheDocument();

    await userEvent.click(screen.getByLabelText("Mostrar inativos"));

    expect(await screen.findByText("Carlos Dias")).toBeInTheDocument();
    expect(screen.getByText("[ inativo ]")).toBeInTheDocument();
    expect(screen.queryByText("Ana Lima")).not.toBeInTheDocument();
  });

  it("marca quem ainda não definiu senha", async () => {
    autenticarComo("diretor");
    responder([usuario({ senha_definida: false })]);
    renderizar(<UsuariosPage />);

    expect(await screen.findByText("aguardando senha")).toBeInTheDocument();
  });

  it("não oferece desativar a própria conta", async () => {
    // `autenticarComo` forja o token com user_id 1 — o mesmo id da Ana.
    autenticarComo("diretor");
    responder([usuario(), usuario({ id: 2, username: "bia", first_name: "Bia", last_name: "Souza" })]);
    renderizar(<UsuariosPage />);

    await screen.findByText("Ana Lima");
    await userEvent.click(screen.getByRole("button", { name: "Ações de ana.sec" }));
    expect(screen.getByText("Editar")).toBeInTheDocument();
    expect(screen.queryByText("Desativar")).not.toBeInTheDocument();

    await userEvent.keyboard("{Escape}");
    await userEvent.click(screen.getByRole("button", { name: "Ações de bia" }));
    expect(await screen.findByText("Desativar")).toBeInTheDocument();
  });

  it("linka pra ficha só de quem é professor", async () => {
    autenticarComo("diretor");
    responder(
      [
        usuario({ id: 2, username: "bia", first_name: "Bia", last_name: "Souza", perfil: "professor" }),
        usuario({ id: 3, username: "ivo", first_name: "Ivo", last_name: "Reis", perfil: "inspetor" }),
      ],
      [{ id: 77, usuario: 2, ativo: true }],
    );
    renderizar(<UsuariosPage />);

    await screen.findByText("Bia Souza");
    await userEvent.click(screen.getByRole("button", { name: "Ações de bia" }));
    // `DropdownMenuItem asChild` repassa `role="menuitem"` pro <a>, então
    // ele não responde como `link` — o href é o que importa aqui.
    expect(
      await screen.findByRole("menuitem", { name: "Ver ficha do professor" }),
    ).toHaveAttribute("href", "/professores/77");

    // A outra metade: sem ela, renderizar o item pra todo mundo passaria
    // (teste de mutação pegou exatamente isso). O Ivo é inspetor e não
    // tem ficha — oferecer o link mandaria pra uma rota inexistente.
    await userEvent.keyboard("{Escape}");
    await userEvent.click(screen.getByRole("button", { name: "Ações de ivo" }));
    expect(await screen.findByText("Editar")).toBeInTheDocument();
    expect(
      screen.queryByRole("menuitem", { name: "Ver ficha do professor" }),
    ).not.toBeInTheDocument();
  });

  it("abre o dialog de novo usuário avisando que a conta nasce sem senha", async () => {
    // A composição do select de perfil é testada direto em
    // `features/usuarios/constants.test.ts`: o Radix só renderiza as
    // opções com o select aberto, e abri-lo em jsdom é frágil.
    autenticarComo("diretor");
    responder([usuario()]);
    renderizar(<UsuariosPage />);

    await screen.findByText("Ana Lima");
    await userEvent.click(screen.getByRole("button", { name: "Novo usuário" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/nasce sem senha/)).toBeInTheDocument();
    expect(within(dialog).getByLabelText("Usuário")).toBeInTheDocument();
  });

  it("não some com o atalho da ficha em silêncio quando ele falha ao carregar", async () => {
    // `isLoading` volta a false quando a query falha, então sem o guard
    // o mapa fica vazio e o item some como se a pessoa não tivesse
    // ficha. Ver "Query que falha não vira estado vazio" no CLAUDE.md.
    autenticarComo("diretor");
    servidor.use(
      http.get(`${API}/usuarios/`, () =>
        HttpResponse.json([
          usuario({ id: 2, username: "bia", first_name: "Bia", last_name: "Souza", perfil: "professor" }),
        ]),
      ),
      http.get(`${API}/professores/`, () => new HttpResponse(null, { status: 500 })),
      http.get(`${API}/escolas/`, () =>
        HttpResponse.json([{ id: 1, nome: "Escola Teste" }]),
      ),
    );
    renderizar(<UsuariosPage />);

    // Controle positivo: a lista de usuários carregou, então o que falta
    // abaixo é consequência da falha das fichas, não de tela vazia.
    expect(await screen.findByText("Bia Souza")).toBeInTheDocument();
    expect(
      await screen.findByText(/não foi possível carregar as fichas/i),
    ).toBeInTheDocument();
  });

  it("avisa e trava o envio quando as escolas não carregam, só pro admin global", async () => {
    // O select de escola só existe pro admin global; contar a falha de
    // `/escolas/` sem esse gate travaria a direção por causa de uma
    // lista que ela nem consome. Ver o AlertaOpcoesIndisponiveis.
    autenticarComo("admin", null);
    servidor.use(
      http.get(`${API}/usuarios/`, () => HttpResponse.json([usuario()])),
      http.get(`${API}/professores/`, () => HttpResponse.json([])),
      http.get(`${API}/escolas/`, () => new HttpResponse(null, { status: 500 })),
    );
    renderizar(<UsuariosPage />);

    await screen.findByText("Ana Lima");
    await userEvent.click(screen.getByRole("button", { name: "Novo usuário" }));

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByText(/não foi possível carregar as opções/i),
    ).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Salvar" })).toBeDisabled();
  });

  it("não trava a direção quando as escolas falham, porque ela não usa a lista", async () => {
    autenticarComo("diretor");
    servidor.use(
      http.get(`${API}/usuarios/`, () => HttpResponse.json([usuario()])),
      http.get(`${API}/professores/`, () => HttpResponse.json([])),
      http.get(`${API}/escolas/`, () => new HttpResponse(null, { status: 500 })),
    );
    renderizar(<UsuariosPage />);

    await screen.findByText("Ana Lima");
    await userEvent.click(screen.getByRole("button", { name: "Novo usuário" }));

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).queryByText(/não foi possível carregar as opções/i),
    ).not.toBeInTheDocument();
    expect(
      within(dialog).getByRole("button", { name: "Salvar" }),
    ).not.toBeDisabled();
  });

  it("mostra a recusa do backend em vez de um erro genérico", async () => {
    autenticarComo("diretor");
    responder([usuario()]);
    servidor.use(
      http.post(`${API}/usuarios/`, () =>
        HttpResponse.json(
          { perfil: ["Apenas um administrador pode criar ou promover conta com este perfil."] },
          { status: 400 },
        ),
      ),
    );
    renderizar(<UsuariosPage />);

    await screen.findByText("Ana Lima");
    await userEvent.click(screen.getByRole("button", { name: "Novo usuário" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Usuário"), "novo");
    await userEvent.type(within(dialog).getByLabelText("Email"), "n@e.test");
    await userEvent.click(within(dialog).getByRole("button", { name: "Salvar" }));

    expect(
      await screen.findByText(
        "Apenas um administrador pode criar ou promover conta com este perfil.",
      ),
    ).toBeInTheDocument();
  });
});
