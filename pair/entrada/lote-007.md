# Lote 007

Escrito pelo revisor externo em 2026-11-17, depois de ler a `main` no
commit `8447d61` e rodar os 385 testes (passam).

## Para uma sessão que começa sem contexto

Leia primeiro `pair/ESTADO.md`, `CLAUDE.md` e `docs/decisoes.md`.

## Como processar este arquivo

1. Salve este arquivo, sem alterar, em `pair/entrada/lote-007.md`.
2. Execute "Arrumação" e faça um commit só para ela.
3. Crie `pair/goals/014-codigo-em-ingles.md` com o texto do goal e
   execute-o.

## Revisão do goal 013

Aceito. A junção entrou como previsto (quatro merges sem squash, 337
testes) e a conferência fechou: números inalterados onde não devia mudar,
e a soma por origem igual à do diário 009.

Os critérios 4 e 5 (uso real e pergunta ao usuário) ficam dispensados.
Ver a decisão de processo abaixo.

## Arrumação

### Decisões a registrar em `docs/decisoes.md`

- **Confirmadas:** a lista "Decisões tomadas aqui, para confirmar" do
  diário 013, como está.
- **Processo: goals não dependem de resposta do usuário na sessão.**
  Critério de aceite que exige pergunta ao usuário deixa de ser usado. O
  uso real da ferramenta é feito pelo usuário quando ele quiser.
  *Motivo: o usuário pulou os critérios 4 e 5 do goal 013; interromper a
  sessão para perguntar custa mais do que rende.*
- **E17. Orçamento de evals (padrão do revisor, a recalibrar).** Primeira
  rodada com 5 casos, 2 condições (sem harness e com harness) e 3
  execuções por caso e condição. Teto de 5 milhões de tokens por execução
  e de 100 milhões por rodada; execução que estoura o teto é interrompida
  e conta como falha. Rodada completa só quando o harness ou o modelo
  mudar. Antes de fixar os tetos, uma rodada de calibração com uma
  execução por caso; os tetos passam a ser o dobro do observado. Mesmo
  modelo do trabalho real. *Motivo: mediana de 1,35 milhão de tokens por
  pedido e cerca de 53 milhões por dia no histórico medido.*
- **E18. Idioma.** Código e mensagens de commit em inglês; interface em
  português. Detalhe no goal 014. *Motivo: decisão do usuário em
  2026-11-17.*

### Branches

As branches `goal-009` a `goal-012` estão incorporadas. Apague-as do
remoto (`git push origin --delete goal-009` e as outras três) e, se
existirem, as locais.

### Estado

Atualize `pair/ESTADO.md`: goal 013 aceito, critérios 4 e 5 dispensados.

## Goal 014: código em inglês

Objetivo: passar o código para inglês sem mudar nenhum comportamento. É
uma troca mecânica de nomes. Não aproveite para refatorar, corrigir ou
melhorar nada; o que você notar pelo caminho vai para o diário como
sugestão.

### O que passa para inglês

- nomes de módulos, pacotes e arquivos de código e de teste;
- classes, funções, métodos, parâmetros, variáveis, constantes e
  exceções;
- valores internos de enumeração (por exemplo, os tipos de intervenção e
  de desfecho de hook);
- comentários e docstrings;
- nomes de testes, de arquivos sintéticos e do gerador deles;
- o formato dos casos de eval: nomes de campos e a pasta `evals/casos/`,
  que vira `evals/cases/`. O caso gravado é convertido;
- mensagens de commit, deste goal em diante.

### O que fica em português

- o texto do relatório e toda mensagem impressa pelos comandos, inclusive
  a ajuda;
- os nomes dos comandos e das opções: `dark auditar`, `minerar`,
  `validar`, `--dias`, `--ate`, `--todos`, `--saida`, `--sem-git`,
  `--config`, `--excluir-pasta`, `--nomes` e os demais;
- `docs/`, `pair/`, `README.md`, `evals/README.md` e o `CLAUDE.md`;
- os diários e documentos antigos, que não são reescritos.

Onde um valor interno era impresso direto no relatório, a tradução para
o texto em português passa a ser feita na camada de apresentação.

### Glossário obrigatório

Use estas traduções em todo o código. Para termo que não está aqui,
escolha uma tradução, use-a de forma consistente e acrescente-a ao
glossário.

Módulos:

| Hoje | Passa a ser |
|---|---|
| `leitor` | `reader` |
| `indicadores` | `indicators` |
| `auditoria` | `audit` |
| `relatorio` | `report` |
| `inventario` | `inventory` |
| `contexto` | `context_usage` |
| `historico` | `git_history` |
| `ligacao` | `commit_linking` |
| `origem` | `provenance` |
| `evals/caso` | `evals/case` |
| `evals/mineracao` | `evals/mining` |
| `evals/validacao` | `evals/validation` |

Domínio:

| Português | Inglês |
|---|---|
| sessão | session |
| pedido (de origem humana, E9) | prompt |
| tarefa | task |
| resposta | response |
| chamada de ferramenta | tool call |
| resultado de ferramenta | tool result |
| subagente | subagent |
| intervenção | intervention |
| interrupção, rejeição, mensagem no meio do turno | interruption, rejection, mid-turn message |
| desfecho de hook | hook outcome |
| bloqueio, confirmação, parada | block, confirmation, stop |
| peso fixo | fixed context |
| repartição | breakdown |
| plataforma, harness, não explicado | platform, harness, unexplained |
| peso morto | dead weight |
| disponível, usado, nunca usado | available, used, never used |
| custo | cost |
| achado | finding |
| origem (de uma peça) | provenance |
| peça (do inventário) | harness item |
| escopo | scope |
| instrução | instruction |
| ligação (sessão a commit) | commit link |
| janela | window |
| ambíguo | ambiguous |
| reversão, retoque | revert, retouch |
| falha de leitura | read failure |
| desconhecido (tipo ou campo) | unknown |
| copiada (por fork), sintética | copied, synthetic |
| sessão de comando local | local-command session |
| identidade (do repositório) | repository identity |
| corte (`--ate`) | cutoff |
| conferência cruzada | cross-check |

"Pedido" vira `prompt`, e não `request`, porque `request` já nomeia a
requisição à API nos registros (`api-request`).

### Como fazer

- Antes de alterar qualquer coisa, grave em `local/` a saída de cada
  comando existente sobre as mesmas entradas, para comparar depois: a
  auditoria sobre os arquivos sintéticos e sobre os dados reais (com
  `--todos`, o corte do goal 002, sem as pastas dos experimentos e com
  `--sem-git`), o inventário, a mineração e a validação do caso gravado,
  e os comandos de conferência do leitor e dos indicadores.
- Renomeie arquivos com `git mv`, para o histórico acompanhar.
- Vários commits, por área, cada um com todos os testes passando.
- Nenhum teste é apagado, pulado ou enfraquecido.

### Critério de aceite

1. Os 385 testes passam, com os nomes novos. O número não diminui.
2. **Saída idêntica.** Cada saída gravada antes é igual, byte a byte, à
   saída do mesmo comando depois. Onde o nome do comando mudou por causa
   do módulo (`python -m dark.leitor` vira `python -m dark.reader`), a
   comparação é da saída. Mostre no diário a lista dos comandos
   comparados e o resultado de cada `diff`.
3. **Nada sobrou.** Procure em `src/` e `tests/` cada termo da coluna em
   português do glossário e cada nome antigo de módulo. O que restar tem
   de ser texto de interface; liste no diário as ocorrências restantes,
   por arquivo, com a justificativa.
4. `docs/glossario.md`: o glossário final, incluindo os termos que você
   acrescentou e o mapa de nomes antigos para novos das classes e
   funções principais, para que os diários antigos continuem legíveis.
5. `README.md` e `CLAUDE.md` com os comandos e caminhos novos. No
   `CLAUDE.md`, uma seção "Convenções" com a regra de idioma (E18) e o
   motivo.

No diário, que continua em português: os termos que você acrescentou ao
glossário; onde a separação entre valor interno e texto de interface
exigiu código novo; e as sugestões de melhoria que você anotou e não fez.
