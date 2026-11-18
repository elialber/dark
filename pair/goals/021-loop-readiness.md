# Goal 021 — Laço pronto para rodar

Lote: [009](../entrada/lote-009.md) (na `main`, depois da junção dos
goals 018 e 020)
Data: 2026-11-17

## Objetivo

Fechar o que a revisão encontrou antes da primeira rodada sem
supervisão, e ligar o executor de evals ao comando.

1. **Push pelo orquestrador.** O revisor do laço deixa de fazer push; o
   hook bloqueia o push do revisor; o orquestrador faz o push depois dos
   testes e da conferência do histórico. Ajuste a definição do revisor,
   os textos das sessões e `docs/laco-de-par.md`.
2. **Hook.** Bloqueie, para os agentes do laço, a alteração de
   configuração do git que executa código ou muda o comportamento dos
   comandos (`core.hooksPath`, `alias.*`, `core.sshCommand` e
   semelhantes).
3. **Conferência de arquivos protegidos por conteúdo.** Depois de cada
   sessão, o orquestrador confere que os arquivos protegidos têm o mesmo
   conteúdo de antes, na árvore de trabalho e não só no histórico, para
   pegar a escrita que o hook não vê. Diferença: a rodada para.
4. **Executor no comando.** Aplique as mudanças propostas no diário 020:
   os subcomandos do executor em `python -m dark.evals`; a validação
   passa a encerrar processos pela mesma função do executor, sem a
   chamada que só existe em um sistema; `evals/README.md`, a docstring do
   pacote e `docs/glossario.md` atualizados.

## Requisitos

Testes antes do código; nada além do listado.

## Critério de aceite

1. Os testes passam. O workflow de testes passa nos seis jobs; mostre a
   tabela.
2. Há teste para cada item: revisor não consegue fazer push; alteração
   de `core.hooksPath` bloqueada; rodada para quando um arquivo protegido
   muda de conteúdo sem passar pelo git; `python -m dark.evals` lista os
   subcomandos novos.
3. `python -m dark.evals validar` sobre o caso gravado dá a mesma saída
   de antes.

## Diário

Em português: o que mudou no laço e o que você ainda mudaria antes de
deixá-lo rodar por três ciclos.
