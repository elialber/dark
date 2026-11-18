# Goal 047 — Documentos do módulo Graphify

Lote 019, rodada 004, ciclo 3. O módulo `graphify` (goal 044) entrou na
`main` sem documentação; este goal faz para ele o que o goal 046 fez
para o Langfuse.

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

