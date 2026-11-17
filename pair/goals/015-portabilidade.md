# Goal 015 — Portabilidade

Texto do goal, como veio no [lote 007b](../entrada/lote-007b.md) (lote
paralelo, em worktree próprio, branch `goal-015`, ao mesmo tempo que a
renomeação do lote 007).

Objetivo: medir o quanto o código depende do ambiente em que foi
construído (uma máquina, Linux sob WSL2, Claude Code em linha de
comando, 15 versões de um mês). O goal não corrige nada; as correções
vêm depois da renomeação.

## Parte A: testes em três sistemas

`.github/workflows/tests.yml`:

- matriz com Ubuntu, macOS e Windows, em Python 3.12 e 3.13;
- instala o pacote com o extra de desenvolvimento e roda os testes;
- dispara em push para qualquer branch e em pull request;
- actions de terceiros fixadas por versão;
- uma falha em um sistema não cancela os outros.

Push da branch e leitura do resultado. Sem corrigir as falhas: por
sistema e versão, quantos testes passam, quais falham e a causa provável,
agrupada por tipo (separador de caminho, letra de unidade, diferença de
maiúsculas, quebra de linha, codificação do terminal, comando ausente,
grupo de processos, outro).

## Parte B: levantamento das suposições de ambiente

`docs/portabilidade.md`, a partir da leitura do código. Para cada
suposição: o que o código supõe e em que módulo (nome atual e novo); de
onde veio (documentação oficial ou observação); o efeito em outro
ambiente (bloqueia, degrada ou cosmético); a proposta (configurável,
detecção em tempo de execução ou degradar com aviso).

Categorias mínimas: sistema e caminhos; Claude Code; listas e limiares
tirados da amostra; repositório auditado; execução de processos;
localidade; dados por máquina. Fecha com a lista ordenada do que impede
macOS, do que impede Windows nativo e do que só reduz a qualidade.

## Critério de aceite

1. O workflow existe na branch e rodou, ou o diário diz por que não foi
   possível ler o resultado.
2. `docs/portabilidade.md` cobre as sete categorias, e cada suposição tem
   os quatro campos.
3. Nenhum arquivo existente foi alterado.

No diário: a tabela de resultados por sistema; as três suposições mais
perigosas; o que não deu para avaliar só lendo o código.

## Regras de convivência

Só arquivos novos; nenhum arquivo existente editado; sem merge; não
atualizar `pair/ESTADO.md`. Código, configuração e mensagens de commit em
inglês (E18); `docs/` e `pair/` em português.
