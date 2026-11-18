# Goal 044: módulo `graphify`

Do [lote 017b](../entrada/lote-017b.md). O item 6 do roteiro pede o
módulo Graphify: um grafo do repositório para o agente consultar, com
skill e hook. Origem e versão vêm da resposta do usuário à decisão D1 da
rodada 003 (`pair/DIRECAO.md`): a edição community (open source)
oficial, na versão mais recente publicada quando o goal for feito,
fixada no módulo. A medição do ganho não faz parte deste goal.

1. **Investigação curta, só o que destrava a entrega** (registre no
   diário, com as URLs e a data da consulta):
   - qual é o projeto Graphify oficial (repositório e pacote publicado),
     sua licença, e a versão mais recente publicada, conferida em **duas
     fontes independentes** (por exemplo, o índice de pacotes e as
     releases ou etiquetas do repositório);
   - o que a instalação oficial dessa versão faz para o Claude Code no
     **escopo do projeto**: que skill, que hook, em que arquivos, com que
     comando; e o que ela faz no escopo do usuário (que o módulo **não**
     vai fazer).
   Fonte: só o repositório e o pacote oficiais. **Não** leia nem copie a
   instalação que exista na máquina (`~/.claude/skills/...` ou outra):
   ela é do usuário, pode estar em outra versão, e o repositório é
   público.
2. **O módulo.** `src/dark/scaffold/graphify.py`, classe `Graphify`
   (nome `graphify`, `version` = a versão fixada do Graphify, indicador
   `cost_per_task`, padrão a confirmar), registrada em `registry.py`. O
   plano cria, no repositório, o equivalente de projeto ao que a
   instalação oficial faz, e nada além:
   - a skill oficial da versão fixada em `.claude/skills/graphify/`
     (texto copiado da versão fixada, com a origem, a versão e a licença
     citadas no topo ou num arquivo ao lado), se a licença permitir a
     cópia; se não permitir, o módulo não copia e o plano diz como
     instalá-la, e o diário registra o motivo;
   - o hook oficial, em `.claude/settings.json` por `JsonEntry`;
   - a linha do diretório de saída do Graphify no `.gitignore`
     (`AppendLine`), se a ferramenta gera arquivos no repositório.
   **Sem** seção no `CLAUDE.md` nem regra nova, mesmo que a instalação
   oficial a escreva: regras nascem de falhas (padrão a confirmar,
   registre no diário o que ficou de fora). O conteúdo fica no código
   Python como texto (constantes), **sem** mudar `pyproject.toml`.
3. **O que o plano imprime.** Como instalar a ferramenta na máquina, com
   versão fixa (por exemplo, `python -m pip install "<pacote>==<versão>"`;
   o módulo não instala) e como gerar o grafo pela primeira vez. Use o
   mecanismo de `reasons` do contrato de módulo ou o que o `cli.py` já
   oferece; se precisar de um campo novo no contrato, mude o mínimo e
   diga no diário. Se o goal 043 fizer o mesmo em paralelo, o revisor
   concilia na junção.
4. **`verify`.** Só lê, sem rede: confere que os arquivos e o hook do
   plano estão lá com o conteúdo aplicado e que o executável do Graphify
   está no `PATH` (por `shutil.which`, sem executá-lo). Ok só se nada
   falta; o motivo diz o que falta.
5. **Ida e volta.** `dark adicionar graphify <repo> --aplicar` e `dark
   remover graphify <repo>` num repositório temporário com `git init`
   deixam a árvore igual byte a byte (conteúdo de todos os arquivos fora
   de `.git`), também quando já existiam `.gitignore` e
   `.claude/settings.json` com conteúdo do usuário, e quando outro módulo
   de teste escreveu no mesmo `.claude/settings.json` (reverter o
   Graphify não mexe no do outro).

## Arquivos que você pode criar ou alterar

- `pair/goals/044-graphify-module.md` e `pair/diario/044.md` (novos);
- `src/dark/scaffold/graphify.py` (novo);
- `src/dark/scaffold/registry.py`: **só** para registrar o módulo, numa
  linha `register(Graphify)` no fim do arquivo (com o import necessário).
  O goal 043, em paralelo, faz o mesmo para o Langfuse; o revisor resolve
  o conflito dessas linhas na junção;
- `src/dark/scaffold/module.py` e `src/dark/scaffold/cli.py` /
  `src/dark/cli.py`, só se o item 3 exigir, no mínimo necessário;
- `tests/test_graphify_module.py` (novo);
- `tests/test_add_modules.py`: **só** a linha
  `assert [m.name for m in list_modules()] == ["base"]`, trocada
  exatamente por `assert "base" in [m.name for m in list_modules()]`
  (o goal 043 faz a mesma troca, idêntica, para não haver conflito).

Nada mais. Em especial, não toque em `pyproject.toml`, `README.md`,
`CHANGELOG.md`, `FUNCIONALIDADES.md`, `docs/`, `plugin/` nem em
`pair/ESTADO.md`.

## Critério de aceite

1. `python -m pytest -q` passa, sem rede e sem o Graphify instalado.
2. Tabela no diário "fonte, versão encontrada, data" com as duas fontes
   independentes do passo 1; a versão do módulo é igual nas duas, ou a
   diferença está explicada.
3. Teste que compara o texto da skill e do hook embarcados com um
   resumo (`sha256`) gravado no teste e anotado no diário junto com a URL
   do arquivo original na versão fixada; o revisor confere o resumo
   baixando o original.
4. Sondagens com a saída no diário: `adicionar graphify` em repositório
   com `.claude/settings.json` inválido; com
   `.claude/skills/graphify/` já existente com conteúdo do usuário
   (conflito, nada aplicado); duas vezes com `--aplicar`; `remover`
   depois de o usuário editar a skill; `verificar` com e sem um
   executável falso `graphify` no `PATH` (criado em diretório
   temporário). Nenhum traceback.
5. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.
