# Lote 007c (paralelo)

Escrito pelo revisor externo em 2026-11-17. Roda em sessão própria, ao
mesmo tempo que o lote 007, que está renomeando todo o código para
inglês na branch principal.

## Regras de convivência

1. **Worktree próprio.** A partir do diretório do repositório:
   `git fetch origin && git worktree add ../dark-goal-016 -b goal-016 origin/main`
   Trabalhe só dentro de `../dark-goal-016`.
2. **Só crie arquivos novos:** `pair/entrada/lote-007c.md` (este arquivo,
   sem alterar), `pair/goals/016-scaffold-engine.md`,
   `pair/diario/016.md`, o pacote `src/dark/scaffold/` e
   `tests/test_scaffold.py`.
3. **Não edite nenhum arquivo existente e não importe nenhum módulo
   existente de `dark`.** A sessão principal está renomeando todos eles.
   Este pacote é autônomo.
4. **Idioma (decisão E18):** código, comentários, nomes de teste e
   mensagens de commit em inglês. Mensagens ao usuário, nomes de comando
   e de opção em português. `pair/` em português.
5. **Não faça merge.** Ao terminar: commit, `git push -u origin goal-016`
   e pare. Não atualize `pair/ESTADO.md`.
6. As regras do `CLAUDE.md` valem: commit sem `-q`; arquivos sintéticos
   que imitam harness são montados em diretório temporário pelo teste,
   nunca gravados com o nome real no repositório.

## Goal 016: motor do scaffold

Objetivo: o mecanismo que aplica mudanças a um repositório de forma não
destrutiva, idempotente e reversível, registrando tudo em um manifesto.
É a base da Fase 4 da especificação. Este goal não instala nenhuma
ferramenta real; os módulos Langfuse e Graphify vêm depois, sobre este
motor.

A ferramenta será usada em repositórios desconhecidos, de qualquer
linguagem e em qualquer sistema. O motor não pode supor nada sobre o
repositório além de ele ser um diretório.

### Operações

No mínimo:

- criar arquivo;
- criar diretório;
- acrescentar uma entrada em um arquivo JSON, em um caminho de chaves
  (por exemplo, um hook na configuração do projeto ou um servidor na
  configuração de MCP);
- acrescentar uma linha a um arquivo de texto, se ainda não existir (por
  exemplo, em `.gitignore`);
- inserir um bloco delimitado por marcadores em um arquivo de texto.

### Ciclo

1. **Plano.** Uma lista de operações. Pode ser inspecionado sem alterar
   nada, mostrando o que mudaria em cada arquivo.
2. **Aplicação.** Tudo ou nada: se uma operação do plano não puder ser
   aplicada, nenhuma é.
3. **Manifesto.** Arquivo no repositório que registra cada operação
   aplicada, com o necessário para desfazê-la e a versão fixada de quem a
   pediu.
4. **Reversão.** Desfaz exatamente o que o manifesto registra.

### Garantias, cada uma com teste

- **Nunca sobrescreve.** Se o destino já existe com conteúdo diferente,
  é conflito: nada é aplicado e o conflito é relatado.
- **Idempotente.** Aplicar de novo o mesmo plano não muda nada e relata
  "já aplicado".
- **Reversível sem perda.** Aplicar e reverter, sem edição no meio,
  deixa a árvore idêntica byte a byte, inclusive em arquivo JSON que já
  existia, com a formatação original.
- **Respeita edições do usuário.** Se algo aplicado foi alterado depois,
  a reversão não o remove nem o reescreve: relata e deixa como está.
- **Fica dentro do repositório.** Operação cujo caminho sai do
  repositório, por `..`, caminho absoluto ou link simbólico, é recusada.
- **Preserva o arquivo.** Quebras de linha (LF ou CRLF), ausência de
  quebra no fim e codificação são mantidas.
- **Reversão parcial.** Reverter um módulo não afeta o que outro módulo
  aplicou, mesmo no mesmo arquivo.

### Contrato de módulo

Só a interface, sem implementação real: um módulo declara nome e versão,
produz um plano para um repositório, sabe verificar se está funcionando e
declara qual indicador pretende melhorar. A desinstalação é a reversão
pelo manifesto. Nos testes, um módulo de mentira exercita o contrato.

### Requisitos

- Só biblioteca padrão. Caminhos por `pathlib`; nada de separador fixo.
- Testes antes do código, em diretórios temporários. Nenhum teste toca
  em repositório real nem no diretório do usuário.
- Um comando mínimo, com mensagens em português, para inspecionar,
  aplicar e reverter um plano descrito em arquivo, é aceito.
- Segredos: o motor nunca grava valor de variável de ambiente; uma
  operação pode referir o nome de uma variável.

### Critério de aceite

1. Os testes passam, junto com os já existentes.
2. Um teste percorre vários cenários (repositório vazio; com
   configuração existente; com arquivo CRLF; com dois módulos) e confere,
   por hash de todos os arquivos, que aplicar e reverter devolve a árvore
   ao estado inicial.
3. O diário descreve o formato do manifesto, com um exemplo sintético.

No diário, em português: as decisões de projeto que você tomou; o caso
em que a reversão não consegue ser byte a byte, se houver; e o que o
motor ainda precisaria para instalar um módulo real.
