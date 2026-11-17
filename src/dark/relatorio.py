"""Apresentação da auditoria em Markdown (goal 008).

Recebe a `Auditoria` calculada em `dark.auditoria` e devolve texto. Não
calcula indicador nem lê nada: só formata. Em português, legível direto
no terminal. Cada seção termina com uma linha "Como ler".

O relatório traz nomes reais de skills, ferramentas e servidores: é o
propósito dele, e ele fica na máquina do usuário.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime

from dark import indicadores as ind
from dark import leitor
from dark.auditoria import MODOS_SEM_REJEICAO, Achado, Auditoria

TITULO = "Auditoria do harness"

SECOES = {
    "cabecalho": TITULO,
    "peso-fixo": "Peso fixo",
    "peso-morto": "Peso morto",
    "custo": "Custo",
    "intervencoes": "Intervenções",
    "hooks": "Hooks",
    "commits": "Commits",
}

CATEGORIAS = {
    "skills": "Skills",
    "tipos_subagente": "Tipos de subagente",
    "ferramentas": "Ferramentas",
    "servidores_mcp": "Servidores MCP",
}

TIPOS_DE_HOOK = {
    "sucesso": "saída registrada",
    "erro_sem_bloqueio": "falha sem bloqueio",
    "cancelado": "tempo esgotado",
    "bloqueio": "bloqueio",
    "confirmacao": "pediu confirmação",
    "decisao": "liberou",
    "parada": "resumo de parada",
}


# --------------------------------------------------------------------------
# Formatação
# --------------------------------------------------------------------------

def n(valor: float | int | None) -> str:
    """Número no formato brasileiro: 1.234.567 e 12,5."""
    if valor is None:
        return "—"
    if isinstance(valor, float) and not valor.is_integer():
        inteiro, decimal = f"{valor:,.1f}".split(".")
        return inteiro.replace(",", ".") + "," + decimal
    return f"{int(valor):,}".replace(",", ".")


def pct(parte: float, todo: float) -> str:
    if not todo:
        return "—"
    return f"{100 * parte / todo:.1f}".replace(".", ",") + "%"


def quando(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") + " UTC" if dt else "—"


def ancora(titulo: str) -> str:
    """Âncora no estilo do GitHub: minúsculas, sem pontuação, espaço vira hífen."""
    return "#" + re.sub(r"[^\w\- ]", "", titulo.lower()).replace(" ", "-")


def link(secao: str) -> str:
    titulo = SECOES[secao]
    return f"[{titulo}]({ancora(titulo)})"


def codigo(nomes) -> str:
    return ", ".join(f"`{x}`" for x in sorted(nomes))


def como_ler(texto: str) -> str:
    return f"*Como ler:* {texto}"


# --------------------------------------------------------------------------
# Seções
# --------------------------------------------------------------------------

def _cabecalho(a: Auditoria) -> list[str]:
    linhas = [f"# {TITULO}", ""]
    if a.repositorio is None:
        linhas.append("- Repositório: todos os repositórios (`--todos`)")
    else:
        linhas.append(f"- Repositório: `{a.repositorio}`")
        juntados = [d for d in a.diretorios if d != a.repositorio]
        if juntados:
            linhas.append(f"- Diretórios juntados (mesmo commit inicial): "
                          f"{', '.join(f'`{d}`' for d in a.diretorios)}")
    linhas.append(f"- Período coberto: {quando(a.inicio)} a {quando(a.fim)}")
    recorte = []
    if a.desde:
        recorte.append(f"sessões iniciadas desde {quando(a.desde)}")
    if a.ate:
        recorte.append(f"registros até {quando(a.ate)}")
    if recorte:
        linhas.append(f"- Recorte pedido: {'; '.join(recorte)}")
    linhas.append(f"- Sessões: {n(a.sessoes)} · Pedidos: {n(a.pedidos)}")
    if a.versoes:
        faixa = (a.versoes[0] if len(a.versoes) == 1
                 else f"de {a.versoes[0]} a {a.versoes[-1]}")
        linhas.append(f"- Versões do Claude Code: {len(a.versoes)} ({faixa})")
    linhas.append("- Alcance: a retenção padrão das transcrições é de 30 dias; "
                  "sessões mais antigas podem já ter sido apagadas pelo Claude Code.")
    if a.falhas:
        linhas.append(f"- Falhas de leitura: {len(a.falhas)} arquivo(s) não lido(s)")
        linhas += [f"  - {f}" for f in a.falhas]
    if a.desconhecidos.tipos or a.desconhecidos.campos:
        linhas.append(f"- Formato desconhecido (contado, não é erro): "
                      f"{sum(a.desconhecidos.tipos.values())} registro(s) de tipo "
                      f"desconhecido, {sum(a.desconhecidos.campos.values())} campo(s) "
                      f"desconhecido(s)")
        for nome, qtd in sorted(a.desconhecidos.tipos.items()):
            linhas.append(f"  - tipo `{nome}`: {n(qtd)}")
        for nome, qtd in sorted(a.desconhecidos.campos.items()):
            linhas.append(f"  - campo `{nome}`: {n(qtd)}")
    if not a.sessoes:
        linhas += ["", "Nenhuma sessão encontrada para este repositório no período. "
                   "Repositório sem histórico é um estado normal; o relatório passa a "
                   "ter números depois das primeiras sessões."]
    linhas += ["", como_ler(
        "uma sessão pertence ao repositório cuja raiz git contém o diretório em "
        "que ela rodou (E3); diretórios com o mesmo commit inicial são o mesmo "
        "repositório (E15). Sessão cujo arquivo não pôde ser lido fica fora de "
        "todos os números abaixo; ela é atribuída ao repositório pela pasta onde "
        "está, o que pode deixar alguma de fora.")]
    return linhas


def frase(x: Achado, a: Auditoria) -> str:
    v = x.valores
    if x.regra.startswith("peso_morto."):
        texto = (f"{CATEGORIAS[v['categoria']]}: {n(v['nunca_usados'])} de "
                 f"{n(v['disponiveis'])} disponíveis sem nenhum uso no período.")
    elif x.regra == "peso_fixo":
        texto = (f"Mediana de {n(v['mediana'])} tokens carregados antes de qualquer "
                 f"trabalho, em {n(v['sessoes'])} sessões (de {n(v['minimo'])} a "
                 f"{n(v['maximo'])}).")
    elif x.regra == "commits_sem_hash":
        texto = (f"{n(v['sem_hash'])} de {n(v['chamadas'])} chamadas de commit não "
                 f"deixaram hash registrado (com `-q`: {n(v['silenciosas'])}).")
    elif x.regra == "modo_sem_rejeicao":
        texto = (f"{n(v['pedidos_no_modo'])} de {n(v['pedidos'])} pedidos "
                 f"({pct(v['pedidos_no_modo'], v['pedidos'])}) rodaram em modo de "
                 f"permissão que suprime rejeições ({codigo(v['modos'])}).")
    elif x.regra == "falhas_de_leitura":
        texto = f"{n(v['falhas'])} arquivo(s) de sessão não puderam ser lidos."
    elif x.regra == "formato_desconhecido":
        texto = (f"{n(v['tipos'])} registro(s) de tipo desconhecido e {n(v['campos'])} "
                 f"campo(s) desconhecido(s) nas transcrições.")
    else:
        texto = f"{x.regra}: {v}"
    return f"- {texto} → {link(x.secao)}"


def _atencao(a: Auditoria) -> list[str]:
    linhas = ["## O que chama atenção", ""]
    if a.achados:
        linhas += [frase(x, a) for x in a.achados]
    else:
        linhas.append("Nenhuma regra disparou.")
    linhas += ["", como_ler(
        "cada linha sai de uma regra fixa e só diz um fato com número; não é "
        "nota nem recomendação. A seção indicada traz o detalhe e o limite.")]
    return linhas


def _resumo(r: ind.Resumo) -> str:
    return f"mediana {n(r.mediana)} · mínimo {n(r.minimo)} · máximo {n(r.maximo)}"


def _peso_fixo(a: Auditoria) -> list[str]:
    pf = a.peso_fixo
    linhas = ["## Peso fixo", ""]
    if pf.resumo.n:
        linhas.append(f"Tokens de entrada da primeira resposta: {_resumo(pf.resumo)}.")
        linhas.append(f"Sessões com o dado: {n(pf.resumo.n)}; sem o dado: "
                      f"{n(len(pf.sem_dado))} (fork ou sem resposta do modelo).")
    else:
        linhas.append("Nenhuma sessão com o dado.")
    if a.peso_fixo_semanal:
        linhas += ["", "| Semana | Sessões | Mediana | Mínimo | Máximo |",
                   "|---|---:|---:|---:|---:|"]
        for semana, r in a.peso_fixo_semanal:
            linhas.append(f"| {semana} | {n(r.n)} | {n(r.mediana)} | {n(r.minimo)} | "
                          f"{n(r.maximo)} |")
    linhas += ["", como_ler(
        "é o `usage` da primeira resposta de cada sessão (E11): instruções, "
        "ferramentas, skills anunciadas e o primeiro pedido, que também entra e "
        "varia. A repartição por peça ainda não está disponível. Inclui cache: "
        "é tamanho de contexto, não custo em dinheiro.")]
    return linhas


def _nunca_usadas_ferramentas(c: ind.Categoria) -> list[str]:
    """Ferramentas comuns por nome; as MCP agrupadas por servidor."""
    comuns = sorted(x for x in c.nunca_usados if not leitor.servidor_mcp(x))
    por_servidor_nunca = Counter(leitor.servidor_mcp(x) for x in c.nunca_usados
                                 if leitor.servidor_mcp(x))
    por_servidor_todas = Counter(leitor.servidor_mcp(x) for x in c.disponiveis
                                 if leitor.servidor_mcp(x))
    linhas = []
    if comuns:
        linhas.append(f"  - nunca usadas: {codigo(comuns)}")
    if por_servidor_nunca:
        linhas.append("  - nunca usadas, MCP por servidor: " + ", ".join(
            f"`{s}` {k} de {por_servidor_todas[s]}"
            for s, k in sorted(por_servidor_nunca.items())))
    return linhas


def _peso_morto(a: Auditoria) -> list[str]:
    linhas = ["## Peso morto", "",
              f"Período: {quando(a.inicio)} a {quando(a.fim)}. Os itens nunca usados "
              f"são candidatos a revisar, não itens a remover.", ""]
    for chave, titulo in CATEGORIAS.items():
        c: ind.Categoria = getattr(a.peso_morto, chave)
        linhas.append(f"- **{titulo}**: disponíveis {n(len(c.disponiveis))} · usados "
                      f"{n(len(c.usados))} · nunca usados {n(len(c.nunca_usados))}")
        linhas.append(f"  - por sessão: disponíveis {_resumo(c.resumo_disponiveis)}; "
                      f"usados {_resumo(c.resumo_usados)}")
        if chave == "ferramentas":
            linhas += _nunca_usadas_ferramentas(c)
        elif c.nunca_usados:
            linhas.append(f"  - nunca usados: {codigo(c.nunca_usados)}")
        if c.usados_fora_da_lista:
            linhas.append(f"  - usados sem constar em nenhuma lista: "
                          f"{codigo(c.usados_fora_da_lista)}")
    linhas += ["", como_ler(
        "\"nunca usado\" vale só para o período acima; uma peça de uso raro "
        "parece morta. Uso inclui o que os subagentes chamaram; skill conta por "
        "chamada, por atribuição ou por `/comando`. O disponível é o que foi "
        "anunciado na sessão principal. Hooks e regras de instrução não entram: "
        "não há lista do disponível nas transcrições.")]
    return linhas


def _custo(a: Auditoria) -> list[str]:
    c = a.custo
    linhas = ["## Custo", "",
              f"- Total: {n(c.total.total)} tokens; subagentes {n(c.total.subagentes)} "
              f"({pct(c.total.subagentes, c.total.total)})",
              f"- Por sessão: {_resumo(c.resumo_sessao)}",
              f"- Por pedido: {_resumo(c.resumo_pedido)} ({n(c.resumo_pedido.n)} pedidos)",
              f"- Sem pedido atribuído: {n(c.sem_pedido)} tokens da sessão principal"]
    if a.caros:
        linhas += ["", f"Os {len(a.caros)} pedidos mais caros:", "",
                   "| Início do pedido | Tokens | Subagentes |", "|---|---:|---:|"]
        for p in a.caros:
            linhas.append(f"| {quando(p.inicio)} | {n(p.gasto.total)} | "
                          f"{pct(p.gasto.subagentes, p.gasto.total)} |")
    linhas += ["", como_ler(
        "soma de entrada, saída e cache (criado e lido), uma vez por resposta "
        "(E4). Cache lido entra com o mesmo peso: o número mede volume, não "
        "dinheiro. Trabalho disparado por aviso de tarefa em segundo plano entra "
        "no pedido humano anterior (E9).")]
    return linhas


def _intervencoes(a: Auditoria) -> list[str]:
    it = a.intervencoes
    t = it.total
    com_sinal = sum(1 for x in it.por_pedido.values() if x.sinais)
    modos = sorted(it.por_modo.items(), key=lambda kv: (-kv[1], kv[0]))
    linhas = ["## Intervenções", "",
              f"- Pedidos humanos: {n(t.pedidos)} em {n(a.sessoes)} sessões "
              f"(por sessão: {_resumo(it.resumo_pedidos)})",
              f"- Interrupções: {n(t.interrupcoes)} · rejeições de ferramenta: "
              f"{n(t.rejeicoes)} ({n(t.rejeicoes_com_comentario)} com comentário) · "
              f"mensagens no meio do turno: {n(t.mensagens_no_meio)}",
              f"- Pedidos com algum sinal: {n(com_sinal)} de {n(t.pedidos)} · sessões "
              f"sem nenhum sinal: {n(it.sessoes_sem_sinal)} de {n(a.sessoes)}",
              "- Modo de permissão dos pedidos: " + (", ".join(
                  f"`{m}` {n(k)}" for m, k in modos) or "—"),
              "", "Avisos:", ""]
    sem_rejeicao = a.pedidos_sem_rejeicao
    linhas += [
        "- São contagens cruas, ao lado do número de pedidos. Com tão poucos "
        "eventos, nenhuma taxa ou ordenação de sessões tem sentido.",
        f"- Nos modos {codigo(MODOS_SEM_REJEICAO)} o usuário não é consultado, e a "
        f"rejeição de ferramenta não tem como aparecer: {n(sem_rejeicao)} de "
        f"{n(t.pedidos)} pedidos rodaram assim.",
        "- Atenção: a ausência de sinais não indica ausência de correções. A "
        "correção digitada depois que o turno acaba é só mais um pedido.",
        "- \"Pedidos por tarefa\", a medida mais promissora, ainda não existe: o "
        "critério que agrupa pedidos em tarefa está em aberto (E9).",
        "", como_ler(
            "interrupção e mensagem no meio do turno medem também o hábito de "
            "acompanhar o agente enquanto ele trabalha, não só como ele se saiu.")]
    return linhas


def _hooks(a: Auditoria) -> list[str]:
    h = a.hooks
    linhas = ["## Hooks", ""]
    if not h.total:
        linhas.append("Nenhum desfecho visível de hook no período.")
    else:
        linhas += [f"Desfechos visíveis: {n(h.total)}, em {n(h.sessoes_com_hook)} sessões "
                   f"({n(h.em_subagentes)} em subagentes); bloqueios: {n(h.bloqueios)}.",
                   "", "| Evento | Desfechos visíveis | Por tipo |", "|---|---:|---|"]
        for evento, total in sorted(h.por_evento.items(), key=lambda kv: (-kv[1], kv[0])):
            tipos = sorted(((t, k) for (t, e), k in h.por_tipo_e_evento.items()
                            if e == evento), key=lambda tk: (-tk[1], tk[0]))
            detalhe = ", ".join(f"{TIPOS_DE_HOOK.get(t, t)} {n(k)}" for t, k in tipos)
            linhas.append(f"| `{evento}` | {n(total)} | {detalhe} |")
    linhas += ["", como_ler(
        "só aparece o que o hook deixou visível: saída, falha, bloqueio, tempo "
        "esgotado. Hook que roda bem e calado não deixa registro, então zero "
        "desfechos visíveis não quer dizer que o hook não roda (E6). Evento `?` é "
        "registro que não diz o evento.")]
    return linhas


def _commits(a: Auditoria) -> list[str]:
    c = a.commits
    linhas = ["## Commits", ""]
    if not c.chamadas:
        linhas.append("Nenhuma chamada de `git commit` no período.")
    else:
        linhas += [
            f"- Chamadas de `git commit`: {n(c.chamadas)}, em {n(c.sessoes_com_commit)} "
            f"sessões ({n(c.em_subagentes)} em subagentes)",
            f"- Com hash registrado: {n(c.com_hash)} · sem hash: {n(c.sem_hash)}",
            f"- Silenciosas (`-q` ou `--quiet`): {n(c.silenciosas)} · amends: "
            f"{n(c.amends)} · com erro: {n(c.com_erro)}"]
        if c.aproximadas:
            linhas.append(f"- Detectadas por padrão, sem análise do comando: "
                          f"{n(c.aproximadas)}")
        if c.silenciosas:
            linhas += [
                "", "Efeito das chamadas silenciosas: com `-q` o git não imprime o "
                "hash, e a transcrição não o registra. A ligação da sessão ao commit "
                "passa a depender da janela de horário (E7), que pode ser ambígua e "
                "se perde quando a branch é apagada.",
                "", "Regra que resolve, para o `CLAUDE.md` do repositório: "
                "\"Faça `git commit` sem `-q`.\""]
    linhas += ["", como_ler(
        "conta comandos `git commit` analisados, incluindo os de subagentes; "
        "dentro de `bash -c` ou `eval` não aparecem. Sem hash registrado não quer "
        "dizer que o commit não existe, só que a transcrição não diz qual foi.")]
    return linhas


def _ainda_nao(a: Auditoria) -> list[str]:
    return ["## Ainda não disponível", "",
            "- O que está instalado no repositório (skills, hooks, regras, servidores "
            "MCP configurados).",
            "- A repartição do contexto inicial por peça.",
            "- O retrabalho: commits refeitos ou revertidos depois da sessão.",
            "", como_ler(
                "essas partes estão em desenvolvimento em paralelo e entram no "
                "relatório quando forem juntadas.")]


def markdown(a: Auditoria) -> str:
    partes = [_cabecalho(a)]
    if a.sessoes:
        partes += [_atencao(a), _peso_fixo(a), _peso_morto(a), _custo(a),
                   _intervencoes(a), _hooks(a), _commits(a), _ainda_nao(a)]
    return "\n\n".join("\n".join(p) for p in partes) + "\n"
