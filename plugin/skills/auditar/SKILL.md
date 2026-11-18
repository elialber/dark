---
name: auditar
description: Audita o harness do Claude Code de um repositório com o comando dark instalado. Use quando o usuário pedir para auditar o harness, ver o uso das peças (skills, hooks, servidores MCP) ou o peso do contexto.
---

# Auditar o harness com o `dark`

Esta skill orienta a rodar o `dark` que já está instalado na máquina. Ela
não contém o método da auditoria: o relatório vem do comando.

## 1. Conferir a instalação

Rode `dark --versao`.

- Se imprimir uma versão (`dark 0.x.y`), siga para o passo 2.
- Se o comando não existir (`dark: command not found`), confira com
  `command -v dark` e `python -m pip show dark`. Se o `dark` não estiver
  instalado, **não instale por conta própria**: diga ao usuário que a
  instalação é por `python -m pip install "git+<URL do repositório>"` (a
  URL está no README do projeto) e pare até ele instalar.
- Exceção: se o `dark` estiver instalado, mas for uma versão antiga que não
  reconhece `--versao`, siga para o passo 2; as opções do passo 2 que a
  versão antiga não tiver aparecem em `dark auditar --help`.
- Se o comando `dark` não ficar no `PATH`, `python -m dark` faz o mesmo.

## 2. Rodar a auditoria

Rode `dark auditar` no repositório que o usuário indicou (padrão: o
diretório atual). Passe só as opções que o usuário pediu:

- `--dias N`: só sessões dos últimos N dias;
- `--ate <instante>`: ignora registros depois deste instante (ISO 8601);
- `--todos`: sessões de qualquer repositório;
- `--sem-git`: não consulta o histórico git (mais rápido);
- `--saida <arquivo>`: grava o relatório num arquivo.

`dark auditar --help` lista todas. O comando só lê; não altera o
repositório auditado.

### De onde vêm os números

O relatório diz na linha "Fonte" de onde leu:

- **banco de agregados**: sessões, indicadores e ligações de commit vêm do
  banco local que `dark coletar` grava, inclusive as sessões que o Claude
  Code já apagou. A linha traz a data da última coleta; o que aconteceu
  depois dela não aparece. É o padrão quando o banco existe e conhece o
  repositório.
- **leitura direta**: lê as transcrições e o git. A linha diz por que o
  banco não foi usado (não existe, não conhece o repositório ou não pôde
  ser lido).

Opções que mudam a fonte, para usar só se o usuário pedir ou se a linha
"Fonte" mostrar que o banco está velho:

- `--coletar`: coleta no banco antes de auditar (o mesmo que rodar `dark
  coletar` antes). Use quando a última coleta estiver velha;
- `--direto`: ignora o banco e lê as transcrições e o git. Use para ver só
  o que as transcrições ainda guardam;
- `--banco <arquivo>`: usa outro arquivo de banco (o padrão fica no
  diretório de dados do usuário, nunca dentro de um repositório).

A seção "O que mudou desde a última semana" só aparece quando a fonte é o
banco, e só traz a comparação quando há duas semanas com dados; antes
disso ela diz que ainda não há comparação. Sem banco, ou com `--direto`,
ela não existe.

## 3. Resumir o relatório

- Resuma a partir do que o relatório imprimiu: o que chama atenção, peso
  fixo, peso morto, custo e intervenções.
- **Não invente números.** Cite só valores que aparecem no relatório; se
  algo não está lá, diga que o relatório não traz.
- Num repositório sem sessões o relatório diz isso e para: é um estado
  normal, os números aparecem depois das primeiras sessões.

## 4. Avisar sobre o relatório

O relatório traz nomes reais (skills, ferramentas, arquivos, caminhos da
máquina) e é para ficar com o usuário. Por padrão ele sai na saída padrão,
fora do repositório. Se for usar `--saida`, grave fora do repositório
auditado (ou num caminho ignorado pelo git) e avise o usuário disso.
