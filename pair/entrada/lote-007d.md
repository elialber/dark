# Lote 007d (paralelo)

Escrito pelo revisor externo em 2026-11-17. Roda em sessão própria, ao
mesmo tempo que o lote 007, que está renomeando todo o código para
inglês na branch principal.

## Regras de convivência

1. **Worktree próprio.** A partir do diretório do repositório:
   `git fetch origin && git worktree add ../dark-goal-017 -b goal-017 origin/main`
   Trabalhe só dentro de `../dark-goal-017`.
2. **Só crie arquivos novos:** `pair/entrada/lote-007d.md` (este arquivo,
   sem alterar), `pair/goals/017-aggregate-store.md`,
   `pair/diario/017.md`, o pacote `src/dark/store/` e
   `tests/test_store.py`.
3. **Não edite nenhum arquivo existente e não importe nenhum módulo
   existente de `dark`.** A sessão principal está renomeando todos eles.
   Você pode lê-los para entender os dados; o pacote novo é autônomo e
   define os próprios tipos de entrada.
4. **Idioma (decisão E18):** código, comentários, nomes de teste, nomes
   de tabela e de coluna, e mensagens de commit em inglês. `pair/` em
   português.
5. **Não faça merge.** Ao terminar: commit, `git push -u origin goal-017`
   e pare. Não atualize `pair/ESTADO.md`.
6. As regras do `CLAUDE.md` valem: commit sem `-q`.

## Goal 017: armazenamento de agregados

Objetivo: guardar, fora das transcrições, os números de cada sessão e de
cada coleta, para que a auditoria compare uma semana com a anterior. São
as decisões E2 (agregados persistidos), E10 (coleta semanal e
idempotente) e E14 (só entra o que está em um esquema declarado). A
ligação com o leitor e os indicadores, e o comando de coleta, ficam para
depois da renomeação; aqui entra só o armazenamento e as consultas.

### Por que existe

- As transcrições são apagadas pelo Claude Code depois de 30 dias.
- A ligação entre sessão e commit se perde quando a branch é apagada.
- A consulta ao git leva mais de um minuto em disco montado; feita uma
  vez na coleta e guardada, a auditoria volta a levar segundos.
- A repartição do contexto e o inventário medem o estado do momento.

### O que guardar

Um banco SQLite, pela biblioteca padrão, em um diretório de dados do
usuário próprio de cada sistema operacional. O local é um parâmetro;
nunca fica dentro do repositório auditado. Tabelas para, no mínimo:

- **repositórios:** a identidade (commits iniciais) e o último caminho
  visto;
- **sessões:** identificador, repositório, início, fim, versão do Claude
  Code, número de pedidos, tokens (principal e subagentes), peso fixo
  total e por grupo (plataforma, harness, pedido, não explicado),
  contagens de intervenção, pedidos por modo de permissão, desfechos de
  hook e contagens de formato desconhecido;
- **uso de peças por sessão:** tipo, nome, origem, se estava disponível
  e se foi usada;
- **ligações de commit:** sessão, horário da chamada, hash, como foi
  ligada (registrada, por janela, ambígua, sem ligação), se foi amend e
  se foi revertida depois;
- **retratos do inventário:** data, repositório, tipo, escopo, nome,
  tamanho, tamanho da descrição, itens e itens com motivo;
- **coletas:** quando rodou, versão da ferramenta, o que leu e quantas
  falhas.

### Regras do armazenamento

- **Esquema declarado (E14).** A gravação recusa campo que não está no
  esquema.
- **Nada de conteúdo.** Não há coluna de texto livre. Entram números,
  datas, identificadores, hashes e nomes de ferramenta, skill, subagente
  e servidor. Nome acima de um tamanho máximo é recusado. Não entram
  texto de pedido, comando executado, mensagem de commit, caminho de
  arquivo editado nem saída de ferramenta.
- **Idempotente (E10).** Gravar duas vezes a mesma sessão ou a mesma
  coleta deixa o banco no mesmo estado.
- **Versão de esquema e migração para frente.** Banco de versão mais
  nova que o código é erro claro, não corrupção.
- **Falha explícita.** Banco ilegível ou bloqueado dá erro que diz o que
  fazer, sem perder dados.

### Consultas

Por repositório e por semana ISO, com resultado tipado:

- o resumo da semana e o da anterior, lado a lado: sessões, pedidos,
  mediana do peso fixo e de cada grupo, tokens por pedido, contagens de
  intervenção, taxa de commits ligados;
- o que mudou no inventário entre dois retratos: peças novas, removidas
  e que mudaram de tamanho;
- peças que passaram a ficar sem uso, e as que voltaram a ser usadas;
- há quantas semanas seguidas uma peça está sem uso, contando só as
  semanas em que houve sessão.

### Requisitos

- Só biblioteca padrão.
- Testes antes do código, com banco em diretório temporário. No mínimo:
  gravação repetida; campo fora do esquema; nome longo demais; migração
  de uma versão para a seguinte; banco de versão futura; comparação de
  três semanas com dados sintéticos; semana sem sessão; duas conexões
  abertas ao mesmo tempo; banco corrompido.
- Nenhum dado real no repositório.

### Critério de aceite

1. Os testes passam, junto com os já existentes.
2. O diário traz o esquema, tabela por tabela, e para cada coluna a
   origem prevista do dado nos módulos existentes (pelo nome atual e pelo
   novo; o mapa está abaixo).
3. O diário lista o que os módulos existentes calculam hoje e o esquema
   não guarda, com o motivo, e o que o esquema pede e nenhum módulo
   calcula ainda.

No diário, em português: as decisões de projeto que você tomou; o
tamanho esperado do banco depois de um ano de uso, com a conta; e o que
falta para o comando de coleta.

## Mapa de nomes de módulos (lote 007)

`leitor` → `reader`; `indicadores` → `indicators`; `auditoria` → `audit`;
`relatorio` → `report`; `inventario` → `inventory`; `contexto` →
`context_usage`; `historico` → `git_history`; `ligacao` →
`commit_linking`; `origem` → `provenance`.
