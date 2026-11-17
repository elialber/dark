# Goal 009 — Inventário estático do harness

Texto do goal, como veio no [lote 004b](../entrada/lote-004b.md):


Objetivo: um módulo que lê a configuração do Claude Code e devolve a
lista do que está instalado, sem ler transcrições. É a metade "o que
existe" da auditoria; a metade "o que foi usado" vem do leitor e dos
indicadores.

### Antes de escrever código

Consulte a documentação oficial do Claude Code e registre, no diário,
onde cada tipo de peça pode morar e em que escopos: instruções (inclusive
variantes locais, aninhadas e arquivos importados), skills, subagentes,
hooks, servidores MCP, permissões e plugins. Onde a documentação e o que
você observa nesta máquina divergirem, registre as duas versões. Não
parta de memória: esses locais mudam entre versões.

### O que o inventário devolve

Para cada peça encontrada:

- tipo: instrução, skill, subagente, hook, servidor MCP ou permissão;
- escopo: projeto, usuário ou plugin (com o nome do plugin);
- nome e caminho do arquivo de origem;
- tamanho em caracteres e em linhas;
- para skill e subagente: o tamanho da descrição, separado do corpo;
- para hook: evento, filtro de ferramenta e comando;
- para servidor MCP: nome e tipo de transporte;
- para permissões: modo padrão e número de regras de permitir, negar e
  perguntar.

Para instruções, além do tamanho: número de itens de lista e quantos
trazem um motivo declarado. A detecção de "motivo" é heurística; marque o
resultado como estimativa e explique a regra usada.

### Limites

- **Segredos.** Não leia arquivos de credenciais. Em configuração de
  servidor MCP e de hooks, guarde os nomes das variáveis de ambiente,
  nunca os valores.
- **Somente leitura.** O inventário não altera nenhum arquivo, nem do
  repositório inventariado, nem do diretório do usuário.
- **Entradas injetáveis.** O caminho do repositório e o diretório de
  configuração são parâmetros (respeitando `CLAUDE_CONFIG_DIR` como
  padrão), para que os testes não toquem no ambiente real.
- **Sem dependência do leitor.** O módulo não importa `dark.leitor`.
- Só biblioteca padrão.

### Testes

Escritos antes do código, sobre um repositório e um diretório de
configuração sintéticos em `tests/fixtures/inventario/`. No mínimo:

- uma peça de cada tipo, em cada escopo que a documentação prevê;
- instrução com e sem motivo declarado;
- skill com descrição curta e corpo longo;
- configuração de servidor MCP com variável de ambiente, conferindo que o
  valor não aparece em lugar nenhum do resultado;
- arquivo de configuração malformado: o inventário relata a falha e
  segue com o resto (mesmo princípio da decisão E12 do lote 004);
- repositório sem harness nenhum.

Nenhum nome real de skill, subagente, servidor ou projeto entra no
repositório.

### Critério de aceite

1. Os testes passam, junto com os testes já existentes.
2. Rodado nesta máquina, sobre este repositório e o diretório do
   usuário, o inventário termina sem erro. No diário, só contagens por
   tipo e por escopo.
3. Conferência cruzada: compare o número de skills e de tipos de
   subagente que o inventário encontra com o que as transcrições anunciam
   (74 skills e 16 tipos de subagente, segundo
   `docs/viabilidade-indicadores.md`). Explique a diferença: o que é
   anunciado e não está em arquivo, e o que está em arquivo e não é
   anunciado. Diferença sem explicação é pendência.

Um comando mínimo, `python -m dark.inventario <caminho>`, que imprima as
contagens, é aceito. Relatório formatado fica para o lote 5.

### No diário

Além do padrão (o que foi feito, critérios, revisão para publicação):

- a tabela de locais e escopos tirada da documentação;
- a lista do que você precisaria mudar em arquivos existentes, se houver;
- qual parte do inventário você considera mais frágil.
