# Lote 008

Escrito pelo revisor externo em 2026-11-17, depois de ler a `main` no
commit `a02e06c` e as branches `goal-015`, `goal-016` e `goal-017`.

## Para uma sessão que começa sem contexto

Leia primeiro `pair/ESTADO.md`, `CLAUDE.md`, `docs/decisoes.md` e
`docs/glossario.md`. Código e mensagens de commit em inglês; interface,
`docs/` e `pair/` em português (decisão E18).

## Como processar este arquivo

1. Salve este arquivo, sem alterar, em `pair/entrada/lote-008.md`.
2. Execute "Junção". Um commit de merge por branch.
3. Execute "Arrumação" e faça um commit só para ela.
4. Crie `pair/goals/019-portability-fixes.md` com o texto do goal e
   execute-o.
5. Outras sessões trabalham em paralelo nas branches `goal-018` (laço de
   par) e `goal-020` (executor de evals). Não as altere, não faça merge
   delas e não crie os arquivos que elas criam (`tools/pairloop/`,
   `docs/visao.md`, `docs/roteiro.md`, `docs/origem/`,
   `src/dark/evals/runner.py` e vizinhos).
6. Se um passo estiver bloqueado, registre o motivo no diário e pare.

## O que o revisor conferiu

Em uma cópia do repositório:

- **Goal 014:** os 385 testes passam na `main`; o comando de auditoria
  roda sobre os arquivos sintéticos com a interface em português; os
  nomes antigos de módulo só restam em texto de interface e em um arquivo
  sintético.
- **Branches 015, 016 e 017:** só criaram arquivos. O merge das três
  sobre `a02e06c`, nessa ordem, entra sem conflito, e depois dele passam
  526 testes.

Os goals 014, 015, 016 e 017 estão aceitos.

## Junção

1. Confirme que a `main` está limpa e igual a `origin/main`.
2. Para cada branch, na ordem `goal-015`, `goal-016`, `goal-017`:
   `git merge --no-ff origin/<branch>`. Sem squash e sem rebase.
3. Conflito: pare, não resolva, relate os arquivos.
4. Rode todos os testes. O esperado é 526 passando. Número diferente:
   pare e relate.
5. Push da `main`. Remova os três worktrees e apague as três branches do
   remoto.

## Arrumação

### Decisões a registrar em `docs/decisoes.md`

- **Confirmadas como estão:** as listas de decisões "para confirmar" dos
  diários 014, 016 e 017.
- **Portabilidade (goal 015).** Estado medido: macOS passa em tudo;
  Windows tem 25 falhas, das quais 3 são defeitos do código que impedem o
  uso (codificação da saída no terminal, encerramento de grupo de
  processos, codificação da saída do git), 3 são cosméticas (barra
  invertida em caminho no relatório) e 19 são só dos testes. A correção é
  o goal 019.
- **Limite conhecido do motor do scaffold (goal 016).** Se um módulo cria
  um arquivo acrescentando uma linha e outro módulo pede o mesmo arquivo
  inteiro, reverter o primeiro apaga o arquivo de que o segundo precisa.
  Tem de ser corrigido antes do primeiro módulo real.
- **O que o armazenamento não guarda (goal 017):** a lista da seção
  "Calculado hoje, não guardado" do diário 017 fica aceita como está. O
  que o esquema pede e nenhum módulo calcula ainda é trabalho do comando
  de coleta.

### Outros arquivos

- `README.md`: os pacotes novos (`dark.scaffold`, `dark.store`) e o
  estado da portabilidade, em uma linha.
- `pair/ESTADO.md`: goals 014 a 017 aceitos e incorporados.

## Goal 019: correções de portabilidade

Objetivo: a ferramenta passa a rodar em Linux, macOS e Windows. É o
item que responde à exigência do usuário de usar a ferramenta em outros
ambientes.

### O que corrigir

1. **Os três defeitos que impedem o uso no Windows**, descritos no diário
   015 e em `docs/portabilidade.md`:
   - a saída dos comandos falha quando o terminal não é UTF-8;
   - o encerramento de processos por tempo esgotado usa uma chamada que
     não existe no Windows, e deixa processos filhos vivos;
   - a saída do git é lida com a codificação da localidade.
   Corrija a causa em todo lugar em que ela aparece, não só onde um teste
   falhou: toda leitura de saída de processo e toda escrita em terminal.
2. **Os três defeitos cosméticos:** o relatório escreve caminhos sempre
   com barra normal, em qualquer sistema.
3. **Os 19 testes que falham por causa do próprio teste:** caminhos
   inseridos em JSON sem escapar, caminho do interpretador sem aspas, e
   nome de arquivo proibido no Windows. Corrija o teste; nenhum é
   apagado. Onde o caso não existe em um sistema, o teste é pulado nesse
   sistema, com o motivo.
4. **A dependência de `sh` na validação de casos de eval:** decida,
   registre e implemente. Ou a ferramenta deixa de precisar dele, ou
   detecta a ausência e diz ao usuário o que instalar.
5. **De `docs/portabilidade.md`:** todo item marcado como "bloqueia"; e,
   dos marcados como "degrada", os três que o diário 015 aponta como
   mais perigosos, que passam a degradar com aviso no relatório.

### O que não fazer

Não altere o comportamento em Linux. Não refatore além do necessário.
O que você notar pelo caminho vai para o diário, como sugestão.

### Requisitos

- Testes antes do código, para cada defeito de código corrigido.
- Só biblioteca padrão.
- `docs/portabilidade.md` ganha, em cada item, a situação: resolvido
  (com o commit), com aviso, ou em aberto (com o motivo).

### Critério de aceite

1. O workflow de testes, agora na `main`, passa nos seis jobs (três
   sistemas, duas versões de Python). Leia o resultado da execução e
   mostre a tabela no diário. Se um job falhar por problema do executor
   do GitHub, e não dos testes, diga isso e mostre a execução anterior em
   que ele passou.
2. Em Linux, a saída dos comandos sobre as mesmas entradas é idêntica à
   de antes do goal: a auditoria sobre os arquivos sintéticos e sobre os
   dados reais (corte do goal 002, sem as pastas dos experimentos, com
   `--sem-git`), o inventário e a validação do caso de eval gravado.
   Qualquer diferença, explicada.
3. A lista do que "impede o uso" em `docs/portabilidade.md` não tem item
   em aberto, ou o diário explica o que ficou e por quê.

No diário, em português: o que ainda não foi exercitado em Windows e
macOS por falta de teste que rode lá (por exemplo, dados reais do Claude
Code nesses sistemas), e o que você recomenda para cobrir.
