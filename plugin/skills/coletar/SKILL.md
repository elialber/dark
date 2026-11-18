---
name: coletar
description: Grava no banco local de agregados os números das sessões do Claude Code, com o comando dark instalado. Use quando o usuário pedir para coletar, guardar ou registrar as métricas das sessões.
---

# Coletar agregados com o `dark`

Esta skill orienta a rodar `dark coletar --todos`, com o `dark` já
instalado. Antes, confira com `command -v dark` ou `dark --help`. Se não
estiver instalado, **não instale por conta própria**: diga ao usuário que a
instalação é por `python -m pip install "git+<URL do repositório>"` (a URL
está no README do projeto) e pare.

## Rodar

```bash
dark coletar --todos
```

Para coletar só um repositório, use `dark coletar <caminho>`. O banco fica
no diretório de dados do usuário, nunca dentro de um repositório
(`--banco <arquivo>` escolhe outro lugar).

## O que é gravado

Só agregados: os números de cada sessão, as ligações de commits e o
retrato do inventário do harness. Nenhum texto de conversa é gravado.
Coletar de novo não duplica nada; sessões que o Claude Code já apagou
continuam no banco.

Depois de rodar, informe o que o comando imprimiu, sem acrescentar números
que ele não trouxe.
