---
name: auditar
description: Audita o harness do Claude Code de um repositório com o comando dark instalado. Use quando o usuário pedir para auditar o harness, ver o uso das peças (skills, hooks, servidores MCP) ou o peso do contexto.
---

# Auditar o harness com o `dark`

Esta skill orienta a rodar o `dark` que já está instalado na máquina. Ela
não contém o método da auditoria: o relatório vem do comando.

## 1. Conferir a instalação

Rode `dark --versao`.

- Se imprimir uma versão, siga para o passo 2.
- Se o comando não existir ainda (`dark: command not found`, ou a opção
  `--versao` não for reconhecida), confira com `command -v dark` e
  `python -m pip show dark`. Se o `dark` não estiver instalado, **não
  instale por conta própria**: diga ao usuário que a instalação é por
  `python -m pip install "git+<URL do repositório>"` (a URL está no README
  do projeto) e pare até ele instalar. Se o `dark` estiver instalado, mas
  sem `--versao`, siga para o passo 2.
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
