# Lote 016 (principal)

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 003, ciclo 1),
sobre a `main` com os goals 039 e 041 juntados (o 040 aceito, mas ainda
não junto: ver `pair/rodadas/003/revisao-1.md`). Não há lote paralelo: os
documentos esperam o goal 040 entrar na `main`.

## Para uma sessão que começa sem contexto

Você é o executor do goal 042. O orquestrador já criou o seu worktree, na
branch `goal-042`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/ESTADO.md`, `CLAUDE.md`, `docs/visao.md` (em especial "O
que foi negociado e ficou de fora": o scaffold liga ferramentas e cria
estrutura, **não gera regras nem skills**), `docs/roteiro.md` (item 6),
`pair/goals/016-scaffold-engine.md`, `pair/diario/016.md`,
`pair/diario/036.md`, `src/dark/scaffold/` (todos os arquivos) e
`src/dark/cli.py` (`_init`, `_remove`, `_target_repository`).

Idioma (E18): código, comentários, nomes de teste e commits em inglês;
texto impresso, ajuda, nomes de comandos e opções, diário e goal em
português.

## Por que este goal

O item 6 do roteiro pede `dark adicionar <módulo>`. Hoje `iniciar` e
`remover` só conhecem o módulo `base`, e o contrato de módulo (instalar,
verificar, desinstalar) não tem comando para a parte "verificar" nem um
registro por onde um módulo novo entre. Os módulos de terceiros (Langfuse,
Graphify) dependem de uma decisão do usuário (versão e origem do que
instalar) e **não fazem parte deste goal**: aqui entra só a estrutura que
eles vão usar, provada com um módulo de teste.

## Goal 042: `dark adicionar`, `dark verificar` e registro de módulos

Crie `pair/goals/042-add-modules.md` com o texto desta seção.

1. **Registro.** `scaffold.base.MODULES` vira um registro único, com
   função para consultar (`get_module(nome)`) e listar. Só `base` é
   registrado de fábrica. Um teste registra e remove um módulo falso
   (apenas nos testes, nunca no pacote) para provar o fluxo.
2. **`dark adicionar <módulo> [<caminho>] [--aplicar]`:** mesmo
   comportamento de `iniciar` (plano sem escrever, `--aplicar` aplica,
   tudo ou nada, só na raiz de um repositório git, conflito aborta), mas
   para qualquer módulo registrado. Módulo desconhecido: mensagem em
   português com os conhecidos e código 2. `dark iniciar` continua
   existindo e passa a ser `adicionar base`, com a saída atual
   inalterada (os testes de `iniciar` existentes seguem passando sem
   alteração). Extraia o código comum de `_init` em vez de duplicá-lo.
3. **`dark verificar <módulo> [<caminho>]`:** roda `module.verify` e
   imprime `ok` ou o motivo; código 0 se ok, 1 se não, 2 se o módulo é
   desconhecido ou o caminho não é a raiz de um repositório. Só lê.
4. **`dark adicionar --listar`:** lista os módulos registrados com versão,
   indicador e se estão aplicados no repositório (lendo o manifesto).
5. **Ida e volta.** Teste: repositório temporário com `git init`;
   `adicionar` do módulo falso com `--aplicar`, `verificar` ok, `remover`;
   a árvore volta byte a byte ao estado inicial (compare o conteúdo de
   todos os arquivos fora de `.git`, não só a lista de nomes).

### Arquivos que você pode criar ou alterar

- `pair/goals/042-add-modules.md` e `pair/diario/042.md` (novos);
- `src/dark/cli.py` e `src/dark/scaffold/` (só o necessário);
- `tests/test_scaffold*.py`, `tests/test_cli*.py`, `tests/test_add_modules.py`
  (novo).

Nada mais. Em especial, não toque em `README.md`, `CHANGELOG.md`,
`docs/`, `plugin/`, `evals/`, `src/dark/store/`, nem em
`pair/ESTADO.md`. Se um teste de deriva (plugin, método) quebrar por
causa do comando novo, diga no diário qual e por quê, e ajuste só o
esperado se a quebra for legítima.

### Critério de aceite

1. `python -m pytest -q` passa.
2. Tabela "esperado, obtido" do `--help` de `adicionar` e `verificar` e
   dos códigos de saída, rodados por você: módulo desconhecido, caminho
   fora da raiz, conflito, módulo já aplicado, `--listar` antes e depois.
3. Sondagens com a saída no diário: `adicionar` com nome vazio, com
   caracteres de caminho (`../x`), com `--aplicar` duas vezes, `verificar`
   de módulo nunca aplicado, `remover` de módulo adicionado e depois
   editado pelo usuário. Nenhum traceback.
4. A saída de `dark iniciar` (plano e `--aplicar`) é byte a byte igual à
   da `main`, em dois repositórios temporários (um vazio, um com
   `CLAUDE.md` já existente).
5. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta.
- Teste antes do código. Commits sem `-q`, mensagens em inglês.
- Decisões não previstas: padrão, "padrão a confirmar" no diário.
- Ao terminar: escreva `pair/diario/042.md`, faça commit, `git push -u
  origin goal-042` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
