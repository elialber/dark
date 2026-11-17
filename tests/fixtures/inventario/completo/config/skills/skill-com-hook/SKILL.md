---
description: Skill que declara hook no cabeçalho.
hooks:
  PreToolUse:
    - matcher: Bash
      hooks:
        - type: command
          command: ./checa.sh
---
Corpo.
