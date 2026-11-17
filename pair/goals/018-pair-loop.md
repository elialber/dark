# Goal 018 — Laço de par

Texto do goal, como veio no [lote 007e](../entrada/lote-007e.md), que
traz também os quatro documentos gravados em `docs/visao.md`,
`docs/roteiro.md` e `docs/origem/`.

Objetivo: um orquestrador que roda o ciclo revisar, executar, juntar sem
intervenção humana, por um número limitado de ciclos, e para com um
relatório para o usuário.

## Papéis

- **Orquestrador.** Programa determinístico, só com biblioteca padrão.
  Cria worktrees, inicia sessões, aplica os limites, detecta o fim de cada
  sessão e decide quando a rodada para.
- **Revisor.** Uma sessão nova a cada ciclo, sem memória da anterior. Lê
  tudo, roda testes, escreve só em `pair/`, `docs/decisoes.md` e
  `docs/roteiro.md`, e é o único que faz merge na `main`. Nunca escreve
  código de produto.
- **Executor.** Uma sessão por lote, no próprio worktree e na própria
  branch. Nunca toca na `main` e nunca faz merge.

## Paradas

Ao fim dos ciclos previstos, ou antes: testes falhando depois de uma
junção; conflito de merge; mesmo goal rejeitado duas vezes; limite
atingido; sessão sem diário; violação de regra de privacidade. Nada é
descartado ao parar.

## Limites garantidos por código, cada um com teste

- executor não faz push nem merge na `main`;
- nenhum agente faz push forçado, push para outro remoto ou apaga a
  `main`;
- nenhum agente escreve fora do repositório e dos worktrees;
- o laço não altera a si mesmo (`tools/pairloop/`, definição do revisor,
  hooks, `pair/loop.toml`, `pair/DIRECAO.md`);
- `docs/visao.md` e `docs/origem/` são intocáveis;
- o revisor só escreve em `pair/`, `docs/decisoes.md` e
  `docs/roteiro.md`.

## Critério de aceite

1. Os quatro documentos na branch, com tamanho e SHA-256 da tabela do
   lote; o diário mostra os valores obtidos.
2. Os testes passam, junto com os já existentes.
3. Ensaio real de um ciclo em branch de ensaio, sem tocar na `main`, com
   tempo e gasto no diário; a branch de ensaio é apagada ao fim.
4. O diário lista cada arquivo existente que a junção precisará alterar.
