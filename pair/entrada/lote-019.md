# Lote 019 (principal)

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 004, ciclo 3),
sobre a `main` com os goals 044 (módulo Graphify) e 046 (documentos do
Langfuse) juntados: 1317 testes. Lote paralelo deste ciclo:
`lote-019b.md` (goal 048, correções do motor do scaffold), com arquivos
exclusivos.

## Para uma sessão que começa sem contexto

Você é o executor do goal 047. O orquestrador já criou o seu worktree, na
branch `goal-047`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/DIRECAO.md`, `pair/ESTADO.md`, `CLAUDE.md`,
`docs/visao.md` (em especial "Privacidade", "Scaffold que gera conteúdo"
em "O que foi negociado e ficou de fora" e o item 6 do roteiro),
`README.md` (seção "Preparar o repositório", com a subseção do Langfuse,
que é o modelo), `FUNCIONALIDADES.md`, `CHANGELOG.md`, `docs/metodo.md`
(Anexo A), `docs/glossario.md`, `pair/diario/044.md`, `pair/diario/046.md`,
`src/dark/scaffold/graphify.py` (as constantes e `NOTES`; o corpo da
skill copiada é longo e não precisa ser lido inteiro),
`tests/test_langfuse_docs.py` (modelo dos testes de deriva).

Idioma (E18): documentos, diário e goal em português; código de teste,
nomes de teste e commits em inglês.

## Por que este goal

O módulo `graphify` (goal 044) entrou na `main` sem documentação. Os
documentos ainda dizem que ele não está lá: "O Graphify ainda não está na
`main`" (`docs/metodo.md`, Anexo A) e "goal 044, em integração"
(`FUNCIONALIDADES.md`). É o mesmo trabalho que o goal 046 fez para o
Langfuse.

## Goal 047: documentos do módulo Graphify

Crie `pair/goals/047-graphify-docs.md` com o texto desta seção.

1. **`README.md`**, seção "Preparar o repositório": subseção "Módulo
   `graphify`", no mesmo formato da do Langfuse: o que `dark adicionar
   graphify --aplicar` cria (a skill oficial em `.claude/skills/graphify/`,
   com `LICENSE`, `NOTICE`, `ORIGEM.md` e `.graphify_version`; os hooks
   `PreToolUse` e `SessionStart` no `.claude/settings.json`; a linha
   `graphify-out/` no `.gitignore`), a versão fixada (tirada de
   `graphify.py`; o teste confere), o que o módulo **não** faz (não
   instala o Graphify, não gera o grafo, não escreve `CLAUDE.md`), os
   passos de `NOTES` (instalar com versão fixa, gerar o grafo, conferir) e
   o que `dark verificar graphify` confere. Diga que a skill é cópia sem
   alteração do original, sob Apache-2.0, e que `/graphify` numa sessão
   pode usar um modelo e chave de API (conforme o que `NOTES` e o diário
   044 dizem; não invente). Sobre `dark remover graphify`, diga só que
   desfaz o que o manifesto registra e mantém o que o usuário acrescentou
   ao settings: **não descreva o que acontece com a linha do
   `.gitignore`**, porque o goal 048, em paralelo, muda esse
   comportamento.
2. **`docs/metodo.md`**, Anexo A: a frase "O Graphify ainda não está na
   `main`" passa a dizer que o Graphify é um módulo do `dark` (`dark
   adicionar graphify`) e que o ganho dele ainda não foi medido (o item 6
   do roteiro exige provar ganho em custo e passos de exploração).
3. **`CHANGELOG.md`**, "Não lançado": entrada do goal 044 (e do 047).
4. **`FUNCIONALIDADES.md`** (arquivo do usuário; mude só as marcas, o
   texto ao lado delas e a tabela do resumo): o item do Graphify diz
   "precisa provar ganho"; a medição pede credencial e ainda não foi
   feita, então ele fica 🔧, com o texto "goal 044; falta medir o ganho
   (pede credencial)" ou equivalente curto. Se o resumo mudar, ajuste-o
   (o teste do goal 045 confere).
5. **`docs/glossario.md`**: as palavras novas que a interface do módulo
   imprime e que ainda não estejam lá (por exemplo, "Na máquina", nomes
   internos do módulo que aparecem na saída), no formato existente.
6. **Testes de deriva**, em `tests/test_graphify_docs.py` (novo): a
   versão citada na subseção é `VERSION` de `dark.scaffold.graphify`;
   todo comando de instalação citado (`uv tool install`, `pipx install`,
   `pip install`) é igual a uma linha de `NOTES`; o comando de geração do
   grafo citado é igual ao de `NOTES`; todo caminho `.claude/skills/graphify/…`
   citado é um arquivo do plano do módulo; os eventos de hook citados são
   os do plano. Sondagens embutidas, como no `test_langfuse_docs.py`:
   trocar a versão para `0.9.111` faz o teste falhar; citar um arquivo
   `.claude/skills/graphify/INEXISTENTE.md` faz o teste falhar.

### Arquivos que você pode criar ou alterar

- `pair/goals/047-graphify-docs.md` e `pair/diario/047.md` (novos);
- `README.md`, `CHANGELOG.md`, `FUNCIONALIDADES.md`, `docs/metodo.md`,
  `docs/glossario.md`;
- `tests/test_graphify_docs.py` (novo); `tests/test_features_doc.py` e
  `tests/test_method_doc.py` só se um teste existente quebrar pela mudança
  de texto pedida, com a explicação no diário.

Nada mais. Em especial, não toque em `src/`, `plugin/`,
`tests/test_graphify_module.py`, `tests/test_langfuse_docs.py`,
`tests/test_langfuse_module.py`, `docs/roteiro.md`, `docs/decisoes.md`,
`docs/visao.md`, `docs/origem/` nem em `pair/ESTADO.md`. Se achar um
defeito no módulo, descreva-o no diário; não o corrija.

### Critério de aceite

1. `python -m pytest -q` passa (a `main` tem 1317 testes).
2. Tabela "esperado, obtido" no diário: cada afirmação da subseção contra
   a execução real, num repositório temporário com `git init`, com
   `PYTHONPATH` no `src/` do worktree (`dark adicionar graphify` com e sem
   `--aplicar`, `dark adicionar --listar`, `dark verificar graphify` com e
   sem um executável `graphify` falso no `PATH`, `dark remover graphify`),
   e cada versão e comando citados contra `graphify.py`.
3. As sondagens do item 6, com a saída no diário.
4. `git diff main -- README.md | grep '^@@'` no diário, mostrando que o
   parágrafo inicial do usuário não mudou.
5. Nada contradiz `docs/visao.md` (passagens conferidas no diário; em
   especial, o módulo liga uma ferramenta e não gera regras nem skills
   próprias).
6. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.
   O nome do autor do Graphify só pode aparecer onde já aparece (cópia
   do original, exigida pela licença).

## Regras

- Nenhuma dependência nova. Nenhuma sessão do Claude Code aberta. Não
  instale o Graphify nem rode `graphify` de verdade; use um executável
  falso.
- Commits sem `-q`, mensagens em inglês.
- Decisões não previstas: adote um padrão e registre como "padrão a
  confirmar" no diário.
- Ao terminar: escreva `pair/diario/047.md`, faça commit, `git push -u
  origin goal-047` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
