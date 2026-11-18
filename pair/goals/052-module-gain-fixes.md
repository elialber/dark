# Goal 052 — Correções da medição de ganho de um módulo

Lote [021b](../entrada/lote-021b.md), branch `goal-052`.

1. **Preparação que altera o repositório é recusada.** Depois dos
   comandos de preparação, se algum arquivo **rastreado** da cópia
   mudou, foi apagado, renomeado ou mudou de tipo (inclusive virou link
   simbólico ou diretório), a medição falha com `SetupFailed` (código 1
   no comando, "nada foi rodado" se for na conferência antes da rodada),
   com a lista dos caminhos (no máximo dez, mais "e outros N"). Arquivos
   novos ignorados pelo git seguem permitidos, como hoje. Arquivos novos
   **não** ignorados continuam indo para o commit da preparação (padrão
   do 050), e a saída da conferência os lista numa linha, para quem
   lê saber o que o módulo pôs na cópia.
2. **Linha do acerto em `describe`.** Quando o acerto com o módulo é
   maior, a linha diz "acerto com o módulo: N execução(ões) a mais;
   a regra de ganho mede custo e passos, o acerto só conta para a piora"
   (ou texto equivalente); com queda ou empate, a linha de hoje
   ("queda de acerto: N execução(ões); tolerância: ...") fica como está.
   A regra de decisão não muda.
3. **Testes** em `tests/test_module_gain.py`:
   - `graphify` falso que reescreve um arquivo rastreado: `SetupFailed`,
     o caminho na mensagem, o repositório de origem intacto, e a rodada
     pelo comando (`run_round` ou equivalente usado nos testes) recusada
     antes de qualquer execução do agente;
   - o mesmo para arquivo rastreado apagado e para arquivo rastreado
     trocado por diretório;
   - `graphify` falso que cria um arquivo novo não ignorado: aceito, o
     arquivo está no commit da preparação e aparece na linha da saída;
   - `describe` com acerto maior com o módulo: a linha nova, sem número
     negativo; com queda, a linha antiga.
   Os testes existentes continuam passando sem mudança, ou a mudança
   está explicada no diário.

