# Goal 013 — Auditoria integrada

Texto do goal, como veio no [lote 006](../entrada/lote-006.md):

Objetivo: o relatório passa a separar o que é da plataforma do que é do
usuário, a dizer de onde vem o peso fixo e a mostrar o que está
instalado. É o que faltava para o relatório dizer onde mexer.

## 1. Origem das peças (E16)

- Cada skill, tipo de subagente, ferramenta e servidor MCP anunciado
  ganha uma origem, pelo cruzamento com o inventário do repositório
  auditado e do diretório do usuário.
- No peso morto, os nunca usados aparecem agrupados por origem. Os que
  têm arquivo trazem o caminho.
- "O que chama atenção" conta só o que o usuário pode mudar. O que é da
  plataforma aparece em uma linha à parte, como custo fixo de plataforma.
- Peças instaladas e não anunciadas aparecem como contagem, com a
  explicação de que não pesam na lista mostrada ao modelo.

## 2. Repartição do peso fixo (E11, terceira versão)

- O leitor passa a guardar, por sessão, os tamanhos em caracteres das
  partes do primeiro pedido: prompt de sistema, ferramentas, e cada tipo
  de anexo. Só tamanhos; nenhum conteúdo.
- A seção de peso fixo mostra a repartição estimada em três grupos:
  plataforma (prompt de sistema e ferramentas embutidas), harness (lista
  de skills, lista de subagentes, nomes de ferramentas adiadas,
  instruções de servidores MCP, instruções e memória) e o pedido. O que
  sobrar aparece como "não explicado", com o percentual.
- O fator de conversão e o fato de ser estimativa ficam ditos na seção.

## 3. Commits

- Amend pela regra dos acréscimos da E7.
- Chamada sem hash registrado é ligada pelo histórico git, por janela.
  O relatório mostra: com hash, ligadas por janela, ambíguas e sem
  ligação.
- Reversões e amends dos commits ligados. Retoque não aparece.
- As consultas ao git podem ser lentas em disco montado (o diário 011
  mediu 110 s). Consulte só os commits das sessões selecionadas, e ofereça
  `--sem-git` para pular esta parte.

## 4. O que está instalado

Seção nova, a partir do inventário: contagem por tipo e por escopo; para
as instruções, tamanho, número de itens e quantos trazem motivo, com a
marca de estimativa.

## 5. Ajustes do relatório

Os propostos no diário 008:

- listas longas vão para um apêndice no fim; no corpo ficam a contagem e
  os primeiros nomes;
- o detalhe do formato desconhecido vai para o fim; no cabeçalho, uma
  linha com a contagem;
- sai o "mínimo" dos resumos por sessão do peso morto;
- sai a seção "Ainda não disponível";
- `dark auditar` sem argumento audita o repositório do diretório atual.

## Fora deste goal

Comparação com a semana anterior, coleta, armazenamento, marcar item
como revisado, unificar `evals/git.py` com `historico.py`, e qualquer
uso do `/context` no relatório.

## Requisitos

Testes antes do código, só com arquivos sintéticos. Cálculo separado de
apresentação, como no goal 008. Os módulos `inventario.py` e
`historico.py` podem ser alterados onde a integração exigir; relate cada
alteração.

## Critério de aceite

1. Os testes passam.
2. Conferência: `dark auditar --todos`, no corte do goal 002 e sem as
   pastas dos experimentos. Os números que este goal não muda de
   propósito continuam iguais aos da tabela do diário 008. Para os que
   mudam (amends, sessões excluídas, contagens por origem), a tabela
   mostra antes, depois e o motivo.
3. A soma por origem fecha com o total anunciado: as 74 skills se
   dividem como no diário 009 (49 com arquivo, 9 da conta, 16
   embutidas), ou a diferença é explicada.
4. Uso real: peça ao usuário, na sessão, o caminho do mesmo repositório
   do goal 008. Grave o relatório em `local/`. Não registre o caminho em
   arquivo versionado.
5. Pergunte ao usuário, na sessão, em quantos itens do relatório ele
   pretende agir. Registre no diário só o número.

No diário, além do padrão: quanto do peso fixo ficou em cada grupo e
quanto ficou não explicado, só em números; o tempo do comando com e sem
git; e o que você considera o próximo passo mais útil para o relatório.
