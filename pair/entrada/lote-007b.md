# Lote 007b (paralelo)

Escrito pelo revisor externo em 2026-11-17. Roda em sessão própria, ao
mesmo tempo que o lote 007, que está renomeando todo o código para
inglês na branch principal.

## Regras de convivência

1. **Worktree próprio.** A partir do diretório do repositório:
   `git fetch origin && git worktree add ../dark-goal-015 -b goal-015 origin/main`
   Trabalhe só dentro de `../dark-goal-015`.
2. **Só crie arquivos novos:** `pair/entrada/lote-007b.md` (este arquivo,
   sem alterar), `pair/goals/015-portabilidade.md`, `pair/diario/015.md`,
   `.github/workflows/tests.yml` e `docs/portabilidade.md`.
3. **Não edite nenhum arquivo existente**, nem de código, nem de teste.
   A sessão principal está renomeando todos eles. O que precisar mudar
   vai para o diário, como proposta.
4. **Idioma (decisão E18, que a sessão principal está registrando):**
   código, arquivos de configuração e mensagens de commit em inglês;
   `docs/` e `pair/` em português.
5. **Não faça merge.** Ao terminar: commit, `git push -u origin goal-015`
   e pare. Não atualize `pair/ESTADO.md`.
6. As regras do `CLAUDE.md` valem: commit sem `-q`; sessão de teste com
   `CLAUDE_CONFIG_DIR` descartável.

## Contexto

A ferramenta deve funcionar em outras máquinas e em repositórios que o
autor ainda não conhece. Até aqui, tudo foi verificado em um único
ambiente: uma máquina, Linux sob WSL2, Claude Code em linha de comando,
15 versões de um mês. Este goal mede o quanto o código depende desse
ambiente. Ele não corrige nada: as correções vêm depois da renomeação.

## Goal 015: portabilidade

### Parte A: testes em três sistemas

Crie `.github/workflows/tests.yml`:

- matriz com Ubuntu, macOS e Windows, em Python 3.12 e 3.13;
- instala o pacote com o extra de desenvolvimento e roda os testes;
- dispara em push para qualquer branch e em pull request;
- actions de terceiros fixadas por versão;
- uma falha em um sistema não cancela os outros.

Faça push da branch e leia o resultado da execução (por exemplo, com a
CLI do GitHub, se estiver instalada e autenticada). Se não houver como
ler o resultado nesta máquina, registre isso no diário e siga para a
parte B; o revisor lê depois.

Não corrija as falhas. Para cada sistema e versão, registre: quantos
testes passam, quais falham e a causa provável de cada falha, agrupada
por tipo (separador de caminho, letra de unidade, diferença de
maiúsculas, quebra de linha, codificação do terminal, comando ausente,
grupo de processos, outro).

### Parte B: levantamento das suposições de ambiente

Leia o código, somente leitura, e escreva `docs/portabilidade.md` com
toda suposição ligada ao ambiente em que a ferramenta foi construída.
Para cada uma:

- o que o código supõe e em que módulo (cite o nome atual e o novo; o
  mapa está no fim deste arquivo);
- de onde veio: da documentação oficial, ou observado em uma máquina;
- o que acontece em outro ambiente: bloqueia o uso, degrada o resultado
  ou é cosmético;
- a proposta: tornar configurável, detectar em tempo de execução, ou
  degradar com aviso.

Percorra, no mínimo, estas categorias:

1. **Sistema e caminhos:** separadores, letra de unidade, maiúsculas e
   minúsculas, links simbólicos, discos montados, diretório do usuário,
   e a regra que converte o diretório de trabalho no nome da pasta de
   projeto.
2. **Claude Code:** versões fora do intervalo observado; pontos de
   entrada além da linha de comando (aplicativo, IDE, SDK); locais de
   configuração em cada sistema.
3. **Listas e limiares tirados da amostra:** campos e tipos conhecidos;
   a regra "sem arquivo e sem prefixo é embutida"; os prefixos que
   marcam origem na conta; o fator de caracteres por token; os modos de
   permissão que suprimem rejeições; os prefixos de comando reconhecidos
   antes de `git commit`.
4. **Repositório auditado:** o que depende de linguagem ou ferramenta do
   projeto (padrões de arquivo de teste, comando de aceite, versão do
   git); o que depende de haver remoto, branch padrão ou histórico.
5. **Execução de processos:** o uso de `sh -c`, o encerramento de grupo
   de processos e os limites de tempo, em Windows.
6. **Localidade:** formato de números e datas, fuso, codificação de
   arquivos e do terminal.
7. **Dados por máquina:** as transcrições são locais; o que isso implica
   para quem usa mais de uma máquina.

Feche o documento com uma lista ordenada: o que impede hoje o uso em
macOS, o que impede em Windows nativo, e o que só reduz a qualidade do
resultado.

### Critério de aceite

1. O workflow existe na branch e rodou, ou o diário diz por que não foi
   possível ler o resultado.
2. `docs/portabilidade.md` cobre as sete categorias, e cada suposição tem
   os quatro campos.
3. Nenhum arquivo existente foi alterado.

No diário: a tabela de resultados por sistema; as três suposições que
você considera mais perigosas; e o que não deu para avaliar só lendo o
código.

## Mapa de nomes de módulos (lote 007)

`leitor` → `reader`; `indicadores` → `indicators`; `auditoria` → `audit`;
`relatorio` → `report`; `inventario` → `inventory`; `contexto` →
`context_usage`; `historico` → `git_history`; `ligacao` →
`commit_linking`; `origem` → `provenance`; `evals/caso` → `evals/case`;
`evals/mineracao` → `evals/mining`; `evals/validacao` →
`evals/validation`.
