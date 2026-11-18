# Goal 031 — Plugin conectado ao README e ao comando real

Origem: [lote 012b](../entrada/lote-012b.md), rodada 002, ciclo 2.
Branch: `goal-031`.

## Objetivo

Fechar as pontas deixadas pelos goals 027 e 028: as skills do plugin
descrevem o comando como ele é hoje (`dark --versao`, auditoria pelo banco,
`--direto`, `--coletar`, `--banco`), o README fala do plugin e o
`CHANGELOG.md` tem a linha dele.

## Requisitos

1. `plugin/skills/auditar/SKILL.md`: passo 1 usa `dark --versao` (o caso de
   versão sem `--versao` fica como exceção); descreve a linha "Fonte" do
   relatório (banco ou leitura direta), as opções `--direto`, `--coletar` e
   `--banco`, quando usar cada uma, e que "O que mudou desde a última
   semana" só aparece pelo banco, com duas semanas de dados. Cada opção
   conferida em `dark auditar --help`.
2. `plugin/skills/coletar/SKILL.md`: opções conferidas em `dark coletar
   --help`.
3. Teste de deriva em `tests/test_plugin.py`, escrito antes do código: toda
   opção `--xxx` citada numa skill existe na ajuda do comando que a skill
   atribui a ela (`auditar` ou `coletar`), e `dark --versao` funciona.
4. `README.md`: seção "Plugin" depois de "Evals", sem repetir o
   `plugin/README.md`; o plugin não é instalado pelo pip
   (`claude --plugin-dir <caminho>/plugin`).
5. `CHANGELOG.md`: linhas do plugin (goal 028) e das skills em dia com o
   comando (goal 031) em "Não lançado".
6. Se houver credencial no ambiente, uma sessão real com `dark:auditar`
   (diário); sem credencial, registrar que não deu.

## Fora do escopo

`src/`, `evals/`, `pyproject.toml`, `docs/`, `.github/`, `pair/ESTADO.md` e
a versão do `plugin.json`.

## Critério de aceite

1. `python -m pytest -q` passa.
2. `claude plugin validate plugin` passa.
3. Tabela "esperado, obtido" para cada opção e para as frases sobre o
   relatório ("Fonte", "O que mudou"), conferidas contra `--help` e contra
   um banco sintético.
4. Sondagens: `--inexistente` numa skill faz o teste de deriva falhar;
   tirar a seção "Plugin" do README não quebra nada (dizer se um teste
   deveria cobrir).
5. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.
