# Lote 017 (principal)

Escrito pelo revisor do laço de par em 2026-11-18 (rodada 004, ciclo 1),
sobre a `main` com os goals 039, 041 e 042 juntados. Lotes paralelos deste
ciclo: `lote-017b.md` (goal 044, módulo Graphify) e `lote-017c.md` (goal
045, documentos). Eles não tocam nos seus arquivos, exceto as duas
exceções descritas em "Arquivos que você pode criar ou alterar".

## Para uma sessão que começa sem contexto

Você é o executor do goal 043. O orquestrador já criou o seu worktree, na
branch `goal-043`, a partir da `main`; trabalhe só nele. Leia antes de
começar: `pair/DIRECAO.md` (a resposta do usuário à decisão D1),
`pair/ESTADO.md`, `CLAUDE.md`, `docs/visao.md` (em especial "Privacidade"
e "O que foi negociado e ficou de fora": o scaffold liga ferramentas e
cria estrutura, **não gera regras nem skills**), `docs/roteiro.md` (item
6), `pair/diario/016.md`, `pair/diario/036.md`, `pair/diario/042.md` e
todos os arquivos de `src/dark/scaffold/` (em especial `module.py`,
`base.py`, `operations.py`, `registry.py` e a função `_check_secrets` de
`engine.py`).

Idioma (E18): código, comentários, nomes de teste e commits em inglês;
texto impresso, ajuda, diário e goal em português.

## Por que este goal

O item 6 do roteiro pede o módulo Langfuse: rastros das sessões do Claude
Code numa instância do Langfuse. O usuário respondeu à decisão D1 da
rodada 003 (`pair/DIRECAO.md`): **Langfuse auto-hospedado, embarcado no
módulo como arquivos Docker Compose; origem: a edição community (open
source) oficial; versão: a mais recente publicada quando o goal for
feito, fixada no módulo (nada de `latest`)**.

## Goal 043: módulo `langfuse`

Crie `pair/goals/043-langfuse-module.md` com o texto desta seção.

1. **Investigação curta, só o que destrava a entrega** (registre no
   diário, com as URLs e a data da consulta):
   - a versão mais recente publicada do Langfuse (servidor, imagens
     `langfuse/langfuse` e `langfuse/langfuse-worker`), conferida em
     **duas fontes independentes** (por exemplo, as releases do
     repositório oficial no GitHub e as etiquetas no Docker Hub);
   - o `docker-compose.yml` oficial dessa versão (repositório oficial do
     Langfuse), com os serviços que ele exige (banco, ClickHouse, Redis,
     armazenamento de objetos...) e as versões fixas de cada imagem
     auxiliar;
   - a integração oficial do Langfuse com o Claude Code nessa data
     (plugin, hook ou outra forma documentada pelo Langfuse): o que ela
     instala, em que arquivo, que variáveis de ambiente lê, que
     dependência de execução exige e com que licença o código é
     distribuído. Se não houver integração oficial, diga no diário e use a
     forma documentada nos guias oficiais do Langfuse.
2. **O módulo.** `src/dark/scaffold/langfuse.py`, classe `Langfuse`
   (nome `langfuse`, `version` = a versão fixada do Langfuse, indicador
   `cost_per_task`, padrão a confirmar), registrada em `registry.py`. O
   plano cria, no repositório:
   - `.dark/langfuse/docker-compose.yml`: o compose oficial da versão
     fixada, com **todas** as imagens em etiqueta exata (nada de
     `latest`, nada de etiqueta só de versão maior como `:3`), e com
     todo segredo e senha trocados por referência a variável de ambiente
     (`${NOME:?mensagem}` ou equivalente que o Compose aceite), nunca um
     valor padrão como `mysecret` ou `postgres`;
   - `.dark/langfuse/env.exemplo`: os nomes das variáveis, sem valor,
     cada uma com um comentário de como gerá-la (por exemplo, `openssl
     rand -hex 32`);
   - a ligação com o Claude Code na forma oficial apurada no passo 1,
     no escopo do projeto (`.claude/settings.json` por `JsonEntry`, ou o
     arquivo que a integração usar), referindo as chaves só pelo nome da
     variável;
   - a linha `.dark/langfuse/.env` no `.gitignore` (`AppendLine`).
   O conteúdo dos arquivos fica no código Python como texto (constantes),
   **sem** mudar `pyproject.toml`: assim a roda (`wheel`) leva tudo sem
   configuração de dados de pacote. Cite no topo de cada arquivo gerado a
   origem (URL e versão) e a licença do original.
3. **O que o plano imprime.** Além das operações, o plano diz em
   português: como subir a instância (`docker compose -f
   .dark/langfuse/docker-compose.yml --env-file .dark/langfuse/.env up
   -d`), onde pôr as chaves (o `.env`, ignorado pelo git, e as variáveis
   que a integração lê) e que **o Langfuse guarda o conteúdo das
   conversas na instância do usuário** (o `dark` não guarda; ver
   "Guardar conteúdo de conversas" em `docs/visao.md`). Use o mecanismo
   de `reasons` do contrato de módulo ou o que o `cli.py` já oferece; se
   precisar de um campo novo no contrato, mude o mínimo e diga no diário.
4. **`verify`.** Só lê, sem rede e sem Docker: confere que os arquivos
   do plano estão lá com o conteúdo aplicado, que a ligação com o Claude
   Code está no arquivo e, sem ler valores, quais variáveis de ambiente
   exigidas estão ausentes (o motivo cita os nomes). Ok só se nada falta.
5. **Ida e volta.** `dark adicionar langfuse <repo> --aplicar` e `dark
   remover langfuse <repo>` num repositório temporário com `git init`
   deixam a árvore igual byte a byte (conteúdo de todos os arquivos fora
   de `.git`), também quando já existiam `.gitignore` e
   `.claude/settings.json` com conteúdo do usuário.

### Arquivos que você pode criar ou alterar

- `pair/goals/043-langfuse-module.md` e `pair/diario/043.md` (novos);
- `src/dark/scaffold/langfuse.py` (novo);
- `src/dark/scaffold/registry.py`: **só** para registrar o módulo, numa
  linha `register(Langfuse)` no fim do arquivo (com o import necessário).
  O goal 044, em paralelo, faz o mesmo para o Graphify; o revisor resolve
  o conflito dessas linhas na junção;
- `src/dark/scaffold/module.py` e `src/dark/scaffold/cli.py` /
  `src/dark/cli.py`, só se o item 3 exigir, no mínimo necessário;
- `tests/test_langfuse_module.py` (novo);
- `tests/test_add_modules.py`: **só** a linha
  `assert [m.name for m in list_modules()] == ["base"]`, trocada
  exatamente por `assert "base" in [m.name for m in list_modules()]`
  (o goal 044 faz a mesma troca, idêntica, para não haver conflito).

Nada mais. Em especial, não toque em `pyproject.toml`, `README.md`,
`CHANGELOG.md`, `FUNCIONALIDADES.md`, `docs/`, `plugin/` nem em
`pair/ESTADO.md`. Os documentos do módulo vêm num goal seguinte.

### Critério de aceite

1. `python -m pytest -q` passa, sem rede e sem Docker.
2. Teste que lê o compose gerado e falha se alguma linha `image:` não
   tiver etiqueta exata (sem `latest`, sem só a versão maior), e se
   algum valor de senha, segredo ou chave estiver escrito por extenso em
   vez de referência a variável. Sondagem do próprio teste: um compose
   com `image: langfuse/langfuse:3` e outro com `SALT: mysalt` fazem-no
   falhar (diga no diário como provou).
3. Tabela no diário "fonte, versão encontrada, data" com as duas fontes
   independentes do passo 1; a versão do módulo é igual nas duas, ou a
   diferença está explicada.
4. Se houver Docker na máquina: `docker compose -f
   .dark/langfuse/docker-compose.yml config` (com um `.env` de valores
   de teste no rascunho) passa, com a saída resumida no diário. Se não
   houver, diga no diário; não é bloqueio. **Não suba a instância** nem
   baixe imagens.
5. Sondagens com a saída no diário: `adicionar langfuse` em repositório
   com `.claude/settings.json` inválido; com `.gitignore` em CRLF;
   duas vezes com `--aplicar`; `remover` depois de o usuário editar o
   compose; `verificar` sem as variáveis e com elas (valores falsos só
   no ambiente do comando). Com uma variável de ambiente cujo nome
   contém `SECRET` e valor de 8 ou mais caracteres presente no
   conteúdo, o motor recusa (prova de que o módulo não grava segredo).
   Nenhum traceback.
6. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.

## Regras

- Nenhuma dependência nova no `dark` (`pyproject.toml` intocado). A
  dependência de execução da integração (por exemplo, o SDK do Langfuse)
  é da máquina do usuário: o plano diz como instalá-la, com versão fixa;
  o módulo não a instala.
- Nenhuma sessão do Claude Code aberta. Não grave nada no diretório
  pessoal do usuário (`~/.claude`, `~/.config`...): tudo no worktree ou
  em diretório temporário.
- Teste antes do código. Commits sem `-q`, mensagens em inglês.
- Decisões não previstas: adote um padrão e registre como "padrão a
  confirmar" no diário.
- Ao terminar: escreva `pair/diario/043.md`, faça commit, `git push -u
  origin goal-043` e pare. Não faça merge. **Não atualize
  `pair/ESTADO.md`**, apesar do que diz o `CLAUDE.md`: no laço, o
  revisor atualiza o estado ao juntar.
