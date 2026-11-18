# Goal 028 — Plugin do Claude Code

Origem: [lote 011b](../entrada/lote-011b.md), rodada 002, ciclo 1.
Branch: `goal-028`.

## Objetivo

Tornar a auditoria chamável de dentro de uma sessão do Claude Code, com um
plugin (item 8 do [roteiro](../../docs/roteiro.md)). O plugin não substitui
o pacote: orienta o agente a rodar o `dark` instalado.

## Requisitos

1. `plugin/` é a raiz do plugin: manifesto `.claude-plugin/plugin.json`
   (nome, versão igual à de `pyproject.toml`, descrição) e skills em
   `plugin/skills/<nome>/SKILL.md`.
2. Skill `auditar`: confere se `dark` está instalado (sem instalar sozinha;
   indica `pip install "git+<URL>"`), roda `dark auditar` com as opções
   pedidas, resume o relatório sem inventar números e informa que o
   relatório fica fora do repositório por padrão.
3. Skill `coletar`: orienta `dark coletar --todos` e explica que só
   agregados são gravados.
4. Nenhuma regra, hook ou skill com conteúdo de método além disso; nenhum
   comando arbitrário do usuário; nenhuma chave ou caminho pessoal.
5. `plugin/README.md`: instalar pelo caminho local e atualizar.
6. `tests/test_plugin.py`: manifesto, versão, cabeçalho das skills, limite
   da descrição, privacidade. O wheel não leva o plugin (decisão no diário).
7. Sessão real com o plugin só se houver credencial no ambiente; senão,
   registrar o motivo.

## Critério de aceite

1. `python -m pytest -q` passa.
2. O plugin passa em `claude plugin validate` ou na conferência manual do
   formato, com a fonte citada.
3. Sessão real usando a skill `auditar` sobre os arquivos sintéticos, com
   a saída no diário (ou o motivo de não ter rodado).
4. Sondagens: versão diferente, nome diferente da pasta e caminho
   `/Users/x/...` fazem os testes falharem, com a saída no diário.
5. Nenhum nome real, caminho pessoal ou segredo em arquivo versionado.
