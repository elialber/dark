# Revisão 1 da rodada 003

Revisor do laço, 2026-11-18. Branches: `goal-039`, `goal-040`, `goal-041`
(lotes 015, 015b, 015c, da rodada 002).

## O que conferi

- Cada branch só mudou os arquivos que o lote permitia (`git diff --stat`).
- Cópia limpa em `$PAIRLOOP_SCRATCH`: merge de ensaio dos três, sem
  conflito; `python -m pytest -q`: 1212 passaram.
- Sondagens minhas, além das do diário:
  - `guardar` com `tokens` -1, `true`, `1.0`, `1e30`; `run` = 2^63;
    modelo de 5000 caracteres; modelo com caractere nulo; campo extra;
    data impossível; linha que não é JSON; reimportação. Nenhum
    traceback; cada linha recusada traz número e motivo; as válidas entram
    (2 novas; 1 nova + 1 já existente). Observação: a mensagem da data
    ("month must be in 1..12") vem do Python, sem o nome do campo; pequena,
    vai para depois.
  - `coletar --evals` em diretório, binário, vazio e inexistente: código 2,
    "Nada foi coletado nem gravado", banco não criado. Arquivo repetido na
    linha de comando: conta "já existiam".
  - `guardar --banco` e `coletar --banco` dentro de repositório git:
    mesma recusa, nada gravado.
- Privacidade: busca por caminho pessoal, nome e chave nas linhas
  acrescentadas: vazia.
- Tabelas do diário 039 (modelo por sessão contra `grep` do JSONL; regra
  com 11 cenários): coerentes com o código e os testes.

## Veredictos

- **039: aceito.** Limites e modelo das sessões como pedido; decisões não
  previstas razoáveis e registradas.
- **040: aceito, não junto.** Texto confere com `recommend.py` e `--help`;
  teste de deriva novo. Ao juntar, o `README.md` da `main` tinha alteração
  local não commitada (parágrafo inicial e `FUNCIONALIDADES.md`, obra do
  usuário). O merge recusou e o ensaio mostra conflito real no parágrafo
  inicial. Deixei o working tree como estava e não juntei. O texto de 040
  diz que 039 e 041 estão "em andamento": vira atrasado assim que 040
  entrar; o goal de documentos seguinte corrige.
- **041: aceito.**

## Merge

`goal-039` e `goal-041` juntados (sem squash) e testados na `main`;
`goal-040` pendente. A ordem ficou 039, 041 (a 040 falhou no meio).

## Erros meus

- Tentei juntar sem conferir antes se o working tree da `main` estava
  limpo; a ordem prevista (040 antes de 041) se perdeu. Sem dano.

## Planejado

- Lote 016 (goal 042): `dark adicionar`, `dark verificar` e registro de
  módulos, provados com módulo de teste; Langfuse e Graphify esperam D1.
- Sem lote paralelo: o goal de documentos (039, 041, 042, skill `coletar`
  com `--evals`) depende de 040 estar na `main`.
