# Lote 022 (principal): goal 053, workflow de testes verde nos três sistemas

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 005, ciclo 1),
sobre a `main` em `a208e15` (1419 testes passam no macOS do revisor).
Lote paralelo deste ciclo: `lote-022b.md` (goal 054, `with_module` no
banco), com arquivos exclusivos.

## Para uma sessão que começa sem contexto

Você é o executor do goal 053. O orquestrador já criou o seu worktree, na
branch `goal-053`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/DIRECAO.md`, `pair/ESTADO.md`, `CLAUDE.md`,
`docs/visao.md` ("Privacidade"), `docs/portabilidade.md` (o formato dos
itens), `.github/workflows/tests.yml` e os quatro testes citados abaixo.

Idioma (E18): código, comentários, nomes de teste e commits em inglês;
diário, goal e `docs/` em português.

## Por que este goal

A direção do usuário pede a ferramenta "utilizável em outros ambientes".
O workflow de testes da `main` está **vermelho desde a rodada 002, ciclo 2**
(Windows) e, desde a rodada 004, também no Linux; nenhum revisor conferiu
o resultado, apesar da regra "Testes em três sistemas" do roteiro. Na
última execução da `main` (`a208e15`, execução 44370611205):

| Job | Resultado | Teste |
|---|---|---|
| ubuntu 3.12 e 3.13 | 1 falha | `tests/test_langfuse_module.py::test_docker_compose_config_accepts_the_file`: o teste espera `SALT` no erro do `docker compose config` sem `.env`, mas o compose acusou primeiro `REDIS_AUTH` (a ordem das variáveis faltantes no erro não é estável) |
| windows 3.12 e 3.13 | 4 falhas | o mesmo teste do Docker (acusou `CLICKHOUSE_PASSWORD`); `tests/test_evals.py::test_readme_example_is_a_valid_case` (`UnicodeDecodeError: 'charmap'`: `read_text()` sem `encoding`); `tests/test_module_gain.py::test_new_files_not_ignored_go_in_the_preparation_commit` (conjunto de arquivos novos diferente, com o arquivo `relatório do grafo.md`); `tests/test_module_gain.py::test_command_module_already_in_harness` (saída diz "já existe com conteúdo diferente" em vez de "já está": provável quebra de linha CRLF no checkout da skill) |
| macos 3.12 e 3.13 | cancelados | "The job was not acquired by Runner of type hosted even after multiple attempts": falta de máquina no GitHub, não o código. Na execução anterior, macOS 3.12 passou |
| install (três sistemas) | passaram | |

Leia os logs você mesmo: `gh run view --job <id> --log-failed` (ids pela
`gh run view 44370611205 --json jobs`).

## Goal 053: workflow de testes verde nos três sistemas

Crie `pair/goals/053-ci-green.md` com o texto desta seção.

1. **Causa de cada falha.** Para cada um dos quatro testes, diga no
   diário se a causa está no teste ou no produto, com a evidência (linha
   do log, reprodução local quando der). Reproduza no macOS ou Linux o
   que for possível, por exemplo com `git -c core.autocrlf=true` ou
   `PYTHONIOENCODING`/`locale` de Windows simulados; o que só aparece no
   Windows é conferido pelo workflow da sua branch.
2. **Correção na camada certa.** Defeito de teste: corrija o teste, sem
   afrouxar o que ele confere (o teste do Docker continua exigindo que
   o compose recuse rodar sem os segredos, e que o erro cite um dos
   nomes de `langfuse.COMPOSE_SECRETS`). Defeito de produto (por exemplo,
   o motor do scaffold ver como conflito uma skill igual com CRLF, ou um
   nome de arquivo com acento mal lido do git no Windows): corrija o
   código e acrescente um teste que falha antes da correção em qualquer
   sistema (simulando a condição do Windows), não só no Windows.
3. **Procure o mesmo padrão no resto.** `read_text()` e `write_text()`
   sem `encoding` em `tests/` e `src/`, e `subprocess` com `text=True`
   sem `encoding`, onde o texto pode ter acento: corrija os que estiverem
   nos arquivos que você pode alterar e liste os outros no diário. Não
   transforme isso numa reescrita: só os que podem falhar.
4. **`docs/portabilidade.md`:** um item por defeito de produto achado,
   no formato dos existentes, com a situação "corrigido no goal 053".
5. **Regra no `CLAUDE.md`**, em "Regras derivadas de falhas observadas":
   depois do push da branch, o executor espera o workflow da branch
   (`gh run watch` ou `gh run view`) e põe no diário a tabela "job,
   resultado"; job vermelho é corrigido ou explicado antes de parar.
   **Motivo:** o workflow da `main` ficou vermelho no Windows da rodada
   002 à 005 sem que ninguém notasse (goal 053).

### Arquivos que você pode criar ou alterar

- `pair/goals/053-ci-green.md` e `pair/diario/053.md` (novos);
- `tests/test_evals.py`, `tests/test_langfuse_module.py`,
  `tests/test_module_gain.py`, `tests/test_add_modules.py`,
  `tests/test_evals_ablation.py`, `tests/test_evals_runner.py`,
  `tests/test_portability.py`, `tests/test_scaffold*.py`,
  `tests/conftest.py`, e um arquivo de teste novo, se precisar;
- `src/dark/scaffold/` (qualquer arquivo), `src/dark/evals/module_gain.py`,
  `src/dark/evals/workspace.py`, `src/dark/evals/git.py`,
  `src/dark/evals/ablation.py`;
- `docs/portabilidade.md`, `CLAUDE.md` (só a regra do item 5);
- `.github/workflows/tests.yml` só se a causa estiver nele (por exemplo,
  um tempo-limite), com a explicação no diário.

Nada mais. Em especial, **não toque** em `src/dark/store/`,
`src/dark/evals/rounds.py`, `src/dark/evals/__main__.py`,
`src/dark/cli.py`, `src/dark/recommend.py`, `tests/test_evals_store.py`,
`tests/test_collect_evals.py`, `tests/test_store*.py` (são do lote
022b), nem em `pair/ESTADO.md`. Se a correção de um defeito exigir um
desses arquivos, não a faça: descreva-a no diário, com o arquivo e a
linha, e siga com o resto.

### Critério de aceite

1. `python -m pytest -q` passa no seu worktree (a `main` tem 1419 testes).
2. **Workflow da branch:** depois do último push, a execução do workflow
   `tests` no commit final da branch tem os jobs de Ubuntu e Windows
   (3.12 e 3.13) e os três `install` verdes. macOS verde, ou cancelado
   com a anotação de falta de máquina do GitHub citada no diário (não é
   defeito do código; se for cancelado, rode `gh run rerun --failed`
   uma vez e registre o resultado). Tabela "job, resultado, id da
   execução" no diário.
3. Para cada defeito de produto: o teste novo falha na `main` e passa na
   branch (cole as duas saídas no diário).
4. Tabela "teste, causa, camada (teste ou produto), correção" com as
   quatro falhas, sem diferença não explicada.
5. Nenhum teste existente fica mais fraco: cada asserção removida ou
   mudada é citada no diário com o motivo.
6. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta e
  nenhuma chamada a modelo. Não rode o Graphify de verdade (esta máquina
  tem um `graphify` no `PATH`; os testes usam um falso).
- Em comandos de shell com texto entre crases, use aspas simples ou um
  arquivo: uma crase dentro de aspas duplas executa o que está dentro.
- Não grave nada no diretório pessoal do usuário.
- Pode fazer vários pushes da branch para ver o workflow; cada execução
  no Windows leva uns 13 minutos. Espere com `gh run watch <id>` em
  segundo plano, não com `sleep` em sequência.
- Commits sem `-q`, mensagens em inglês. Não faça `git merge`.
- Decisões não previstas: adote um padrão e registre como "padrão a
  confirmar" no diário.
- Ao terminar: escreva `pair/diario/053.md`, faça commit, `git push -u
  origin goal-053`, confira o workflow (critério 2) e pare. Não faça
  merge. **Não atualize `pair/ESTADO.md`**, apesar do que diz o
  `CLAUDE.md`: no laço, o revisor atualiza o estado ao juntar.
