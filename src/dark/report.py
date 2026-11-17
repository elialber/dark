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

from dark import indicators as ind
from dark import reader
from dark import provenance as org
from dark.audit import MODES_WITHOUT_REJECTION, Finding, Audit

TITLE = "Auditoria do harness"

SECTIONS = {
    "header": TITLE,
    "fixed-context": "Peso fixo",
    "dead-weight": "Peso morto",
    "cost": "Custo",
    "interventions": "Intervenções",
    "hooks": "Hooks",
    "commits": "Commits",
    "installed": "O que está instalado",
    "appendix": "Apêndice",
}

# Quantos nomes uma lista mostra no corpo; o resto vai para o apêndice.
FIRST_NAMES = 5

PROVENANCE_NAMES = {
    "project": "projeto",
    "user": "usuário",
    "plugin": "plugin",
    "managed": "gerenciado",
    "account": "plataforma, da conta",
    "builtin": "plataforma, embutida",
    "no_file": "sem arquivo encontrado",
}

INVENTORY_TYPES = {
    "instruction": "Instrução",
    "skill": "Skill",
    "subagent": "Subagente",
    "hook": "Hook",
    "mcp": "Servidor MCP",
    "permission": "Permissões",
}
INVENTORY_SCOPES = ("project", "user", "plugin", "managed")

CATEGORIES = {
    "skills": "Skills",
    "subagent_types": "Tipos de subagente",
    "tools": "Ferramentas",
    "mcp_servers": "Servidores MCP",
}

HOOK_TYPES = {
    "success": "saída registrada",
    "non_blocking_error": "falha sem bloqueio",
    "cancelled": "tempo esgotado",
    "block": "bloqueio",
    "confirmation": "pediu confirmação",
    "decision": "liberou",
    "stop": "resumo de parada",
}


# --------------------------------------------------------------------------
# Formatação
# --------------------------------------------------------------------------

def n(value: float | int | None) -> str:
    """Número no formato brasileiro: 1.234.567 e 12,5."""
    if value is None:
        return "—"
    if isinstance(value, float) and not value.is_integer():
        integer, decimal = f"{value:,.1f}".split(".")
        return integer.replace(",", ".") + "," + decimal
    return f"{int(value):,}".replace(",", ".")


def pct(part: float, whole: float) -> str:
    if not whole:
        return "—"
    return f"{100 * part / whole:.1f}".replace(".", ",") + "%"


def when(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") + " UTC" if dt else "—"


def anchor(title: str) -> str:
    """Âncora no estilo do GitHub: minúsculas, sem pontuação, espaço vira hífen."""
    return "#" + re.sub(r"[^\w\- ]", "", title.lower()).replace(" ", "-")


def link(section: str) -> str:
    title = SECTIONS[section]
    return f"[{title}]({anchor(title)})"


def code(names) -> str:
    return ", ".join(f"`{x}`" for x in sorted(names))


def how_to_read(text: str) -> str:
    return f"*Como ler:* {text}"


def plural(k: int, one: str, several: str) -> str:
    return f"{n(k)} {one if k == 1 else several}"


def first_items(names, limit: int = FIRST_NAMES) -> str:
    """Os primeiros nomes, em ordem, e quantos ficaram para o apêndice."""
    names = sorted(names)
    text = code(names[:limit])
    if len(names) > limit:
        text += f" e mais {n(len(names) - limit)} (lista completa no {link('appendix')})"
    return text


# --------------------------------------------------------------------------
# Seções
# --------------------------------------------------------------------------

def _header(a: Audit) -> list[str]:
    lines = [f"# {TITLE}", ""]
    if a.repository is None:
        lines.append("- Repositório: todos os repositórios (`--todos`)")
    else:
        lines.append(f"- Repositório: `{a.repository}`")
        merged = [d for d in a.directories if d != a.repository]
        if merged:
            lines.append(f"- Diretórios juntados (mesmo commit inicial): "
                          f"{', '.join(f'`{d}`' for d in a.directories)}")
    lines.append(f"- Período coberto: {when(a.start)} a {when(a.end)}")
    selection_ = []
    if a.since:
        selection_.append(f"sessões iniciadas desde {when(a.since)}")
    if a.cutoff:
        selection_.append(f"registros até {when(a.cutoff)}")
    if selection_:
        lines.append(f"- Recorte pedido: {'; '.join(selection_)}")
    lines.append(f"- Sessões: {n(a.sessions)} · Pedidos: {n(a.prompts)}")
    if a.versions:
        version_range = (a.versions[0] if len(a.versions) == 1
                 else f"de {a.versions[0]} a {a.versions[-1]}")
        lines.append(f"- Versões do Claude Code: {len(a.versions)} ({version_range})")
    lines.append("- Alcance: a retenção padrão das transcrições é de 30 dias; "
                  "sessões mais antigas podem já ter sido apagadas pelo Claude Code.")
    if a.failures:
        lines.append(f"- Falhas de leitura: {len(a.failures)} arquivo(s) não lido(s)")
        lines += [f"  - {f}" for f in a.failures]
    if a.excluded_local_command:
        lines.append(f"- Sessões de comando local, excluídas: {n(a.excluded_local_command)} "
                      f"(sem resposta de modelo; só comandos como `/context`)")
    if a.unknowns.kinds or a.unknowns.fields:
        lines.append(f"- Formato desconhecido (contado, não é erro): "
                      f"{sum(a.unknowns.kinds.values())} registro(s) de tipo "
                      f"desconhecido, {sum(a.unknowns.fields.values())} campo(s) "
                      f"desconhecido(s); detalhe no {link('appendix')}")
    if not a.sessions:
        lines += ["", "Nenhuma sessão encontrada para este repositório no período. "
                   "Repositório sem histórico é um estado normal; o relatório passa a "
                   "ter números depois das primeiras sessões."]
    lines += ["", how_to_read(
        "uma sessão pertence ao repositório cuja raiz git contém o diretório em "
        "que ela rodou (E3); diretórios com o mesmo commit inicial são o mesmo "
        "repositório (E15). Sessão cujo arquivo não pôde ser lido fica fora de "
        "todos os números abaixo; ela é atribuída ao repositório pela pasta onde "
        "está, o que pode deixar alguma de fora.")]
    return lines


def sentence(x: Finding, a: Audit) -> str:
    v = x.values
    if x.rule.startswith("dead_weight."):
        which = " com arquivo" if v.get("with_file_only") else ""
        text = (f"{CATEGORIES[v['category']]}: {n(v['never_used'])} de "
                 f"{n(v['available'])} disponíveis{which} sem nenhum uso no período.")
    elif x.rule == "fixed_context":
        text = (f"Mediana de {n(v['median'])} tokens carregados antes de qualquer "
                 f"trabalho, em {n(v['sessions'])} sessões (de {n(v['minimum'])} a "
                 f"{n(v['maximum'])}).")
    elif x.rule == "commits_without_hash":
        text = (f"{n(v['without_hash'])} de {n(v['calls'])} chamadas de commit não "
                 f"deixaram hash registrado (com `-q`: {n(v['silent'])}).")
    elif x.rule == "mode_without_rejection":
        text = (f"{n(v['prompts_in_mode'])} de {n(v['prompts'])} pedidos "
                 f"({pct(v['prompts_in_mode'], v['prompts'])}) rodaram em modo de "
                 f"permissão que suprime rejeições ({code(v['modes'])}).")
    elif x.rule == "read_failures":
        text = f"{n(v['failures'])} arquivo(s) de sessão não puderam ser lidos."
    elif x.rule == "unknown_format":
        text = (f"{n(v['kinds'])} registro(s) de tipo desconhecido e {n(v['fields'])} "
                 f"campo(s) desconhecido(s) nas transcrições.")
    else:
        text = f"{x.rule}: {v}"
    return f"- {text} → {link(x.section)}"


def _attention(a: Audit) -> list[str]:
    lines = ["## O que chama atenção", ""]
    if a.findings:
        lines += [sentence(x, a) for x in a.findings]
    else:
        lines.append("Nenhuma regra disparou.")
    if a.platform is not None:
        p = a.platform
        lines += ["", "Custo fixo de plataforma, fora da contagem acima (anunciado sem "
                   "arquivo, vem da conta ou do Claude Code): "
                   f"{plural(p['skills'], 'skill', 'skills')}, "
                   f"{plural(p['subagent_types'], 'tipo de subagente', 'tipos de subagente')}, "
                   f"{plural(p['tools'], 'ferramenta', 'ferramentas')} e "
                   f"{plural(p['mcp_servers'], 'servidor MCP', 'servidores MCP')}. "
                   f"→ {link('dead-weight')}"]
    text = ("cada linha sai de uma regra fixa e só diz um fato com número; não é "
             "nota nem recomendação. A seção indicada traz o detalhe e o limite.")
    if a.platform is not None:
        text += (" As linhas de peso morto contam só o que tem arquivo, isto é, o que "
                  "você pode mudar (E16).")
    lines += ["", how_to_read(text)]
    return lines


def _summary(r: ind.Summary) -> str:
    return f"mediana {n(r.median)} · mínimo {n(r.minimum)} · máximo {n(r.maximum)}"


def _summary_without_min(r: ind.Summary) -> str:
    return f"mediana {n(r.median)} · máximo {n(r.maximum)}"


def _fixed_context(a: Audit) -> list[str]:
    pf = a.fixed_context
    lines = ["## Peso fixo", ""]
    if pf.summary.n:
        lines.append(f"Tokens de entrada da primeira resposta: {_summary(pf.summary)}.")
        lines.append(f"Sessões com o dado: {n(pf.summary.n)}; sem o dado: "
                      f"{n(len(pf.without_data))} (fork ou sem resposta do modelo).")
    else:
        lines.append("Nenhuma sessão com o dado.")
    if a.weekly_fixed_context:
        lines += ["", "| Semana | Sessões | Mediana | Mínimo | Máximo |",
                   "|---|---:|---:|---:|---:|"]
        for week, r in a.weekly_fixed_context:
            lines.append(f"| {week} | {n(r.n)} | {n(r.median)} | {n(r.minimum)} | "
                          f"{n(r.maximum)} |")
    lines += _breakdown(a)
    lines += ["", how_to_read(
        "é o `usage` da primeira resposta de cada sessão (E11): instruções, "
        "ferramentas, skills anunciadas e o primeiro pedido, que também entra e "
        "varia. Inclui cache: é tamanho de contexto, não custo em dinheiro. A "
        "repartição é estimativa: mede em caracteres as partes do primeiro pedido "
        "gravadas na transcrição e converte em tokens por um fator fixo.")]
    return lines


GROUP_TITLES = {"plataforma": "Plataforma", "harness": "Harness", "pedido": "Pedido"}


def _breakdown(a: Audit) -> list[str]:
    r = a.breakdown
    if r is None or not r.measured:
        return ["", "Repartição: nenhuma sessão com a forma da requisição gravada."]
    factor = n(r.factor)
    lines = ["", f"Repartição estimada, em {n(len(r.measured))} sessões com a forma da "
              f"requisição gravada ({factor} caracteres por token; é estimativa):", "",
              "| Grupo / parte | Tokens estimados, mediana por sessão | Parcela do peso fixo |",
              "|---|---:|---:|"]
    for group in ind.GROUPS:
        lines.append(f"| **{GROUP_TITLES[group]}** | **{n(round(r.group_summary(group).median))}** "
                      f"| **{pct(r.group_sum(group), r.measured_total)}** |")
        for g, part in ind.PARTS:
            if g == group and group != "pedido":
                lines.append(f"| {part} | {n(round(r.summary(part).median))} | "
                              f"{pct(r.total_sum(part), r.measured_total)} |")
    lines.append(f"| **Não explicado** | **{n(round(r.unexplained_summary().median))}** "
                  f"| **{pct(r.unexplained, r.measured_total)}** |")
    if r.without_shape:
        lines += ["", f"Sessões com peso fixo e sem a forma da requisição, fora da "
                   f"repartição: {n(len(r.without_shape))}."]
    lines += ["", f"Plataforma é o prompt de sistema, as ferramentas embutidas e os anexos "
               f"do próprio Claude Code (ambiente, data, modelo). Harness é o que vem da "
               f"configuração: listas de skills e de subagentes, nomes das ferramentas "
               f"adiadas, ferramentas e instruções de servidores MCP, instruções e "
               f"memória, saída de hooks. O fator de {factor} caracteres por token vem do "
               f"diário 010; caracteres incluem o escape de JSON. O não explicado é o "
               f"medido menos a soma das partes: marcação das mensagens, diferença de "
               f"tokenização e o que a transcrição não grava."]
    return lines


def _never_used_tools(c: ind.Category) -> list[str]:
    """Ferramentas comuns por nome; as MCP agrupadas por servidor."""
    common = sorted(x for x in c.never_used if not reader.mcp_server(x))
    never_by_server = Counter(reader.mcp_server(x) for x in c.never_used
                                 if reader.mcp_server(x))
    all_by_server = Counter(reader.mcp_server(x) for x in c.available
                                 if reader.mcp_server(x))
    lines = []
    if common:
        lines.append(f"  - nunca usadas: {first_items(common)}")
    if never_by_server:
        items = [f"`{s}` {k} de {all_by_server[s]}"
                 for s, k in sorted(never_by_server.items())]
        text = ", ".join(items[:FIRST_NAMES])
        if len(items) > FIRST_NAMES:
            text += (f" e mais {n(len(items) - FIRST_NAMES)} servidores "
                      f"(lista completa no {link('appendix')})")
        lines.append("  - nunca usadas, MCP por servidor: " + text)
    return lines


def _by_provenance(a: Audit, key: str) -> list[str]:
    groups = a.never_used_by_provenance.get(key, {})
    if not groups:
        return []
    parts = [f"{PROVENANCE_NAMES[o]} {n(len(groups[o]))}" for o in org.PROVENANCES if o in groups]
    lines = [f"  - nunca usados, por origem: {', '.join(parts)}"]
    with_file = [x for o in org.PROVENANCES if o in org.WITH_FILE for x in groups.get(o, [])]
    if with_file and key != "tools":
        lines.append(f"  - com arquivo (você pode mudar): {first_items(with_file)}; "
                      f"caminhos no {link('appendix')}")
    return lines


def _dead_weight(a: Audit) -> list[str]:
    lines = ["## Peso morto", "",
              f"Período: {when(a.start)} a {when(a.end)}. Os itens nunca usados "
              f"são candidatos a revisar, não itens a remover.", ""]
    for key, title in CATEGORIES.items():
        c: ind.Category = getattr(a.dead_weight, key)
        lines.append(f"- **{title}**: disponíveis {n(len(c.available))} · usados "
                      f"{n(len(c.used))} · nunca usados {n(len(c.never_used))}")
        lines.append(f"  - por sessão: disponíveis {_summary_without_min(c.available_summary)}; "
                      f"usados {_summary_without_min(c.used_summary)}")
        lines += _by_provenance(a, key)
        if key == "tools":
            lines += _never_used_tools(c)
        elif c.never_used:
            lines.append(f"  - nunca usados: {first_items(c.never_used)}")
        if c.used_outside_list:
            lines.append(f"  - usados sem constar em nenhuma lista: "
                          f"{first_items(c.used_outside_list)}")
    if a.not_announced is not None:
        skills, kinds = a.not_announced["skills"], a.not_announced["subagent_types"]
        hidden = sum(1 for p in skills if p.description and not p.description.model_invocable)
        lines += ["", f"Instaladas e não anunciadas: "
                   f"{plural(len(skills), 'skill', 'skills')} ({n(hidden)} com "
                   f"`disable-model-invocation`) e "
                   f"{plural(len(kinds), 'tipo de subagente', 'tipos de subagente')}; não "
                   f"pesam na lista mostrada ao modelo; continuam acessíveis por `/comando` "
                   f"e ocupam espaço em disco."]
    text = ("\"nunca usado\" vale só para o período acima; uma peça de uso raro "
             "parece morta. Uso inclui o que os subagentes chamaram; skill conta por "
             "chamada, por atribuição ou por `/comando`. O disponível é o que foi "
             "anunciado na sessão principal. Hooks e regras de instrução não entram: "
             "não há lista do disponível nas transcrições.")
    if a.provenance_of is not None:
        text += (" A origem cruza o anúncio com o inventário de agora (E16): o que tem "
                  "arquivo é de projeto, usuário, plugin ou gerenciado; sem arquivo, com "
                  "prefixo, é da conta; sem prefixo, embutido no Claude Code. Uma peça "
                  "apagada depois do período aparece como sem arquivo ou embutida.")
    lines += ["", how_to_read(text)]
    return lines


def _installed(a: Audit) -> list[str]:
    i = a.installed
    lines = ["## O que está instalado", ""]
    if i is None:
        lines += ["Inventário não disponível (repositório inexistente nesta máquina).", "",
                   how_to_read("o inventário lê os arquivos do repositório e do diretório do "
                            "usuário; sem eles não há o que contar.")]
        return lines
    hdr = " | ".join(PROVENANCE_NAMES[e] for e in INVENTORY_SCOPES)
    lines += [f"| Tipo | {hdr} | Total |",
               "|---|" + "---:|" * (len(INVENTORY_SCOPES) + 1)]
    for kind, title in INVENTORY_TYPES.items():
        values = [i.counts[(kind, e)] for e in INVENTORY_SCOPES]
        lines.append(f"| {title} | " + " | ".join(n(v) for v in values)
                      + f" | {n(sum(values))} |")
    ins = i.instructions
    lines += [
        "",
        f"- Instruções carregadas no início: {plural(ins.files, 'arquivo', 'arquivos')}, "
        f"{n(ins.chars)} caracteres (cerca de "
        f"{n(round(ins.chars / ind.CHARS_PER_TOKEN))} tokens), "
        f"{plural(ins.item_count, 'item', 'itens')} de lista, {n(ins.with_reason)} com motivo "
        f"(estimativa).",
        f"- Peças locais (pessoais, fora do controle de versão): {n(i.local_items)} · "
        f"sob demanda (carregam só ao tocar a pasta): {n(i.on_demand)}",
        f"- Plugins: {n(i.active_plugins)} ativos de {n(i.plugins)} instalados",
    ]
    if i.failures:
        lines.append(f"- Arquivos de configuração que não puderam ser lidos: {n(i.failures)}")
    lines += ["", how_to_read(
        "é o estado de agora, lido dos arquivos (repositório, diretório do usuário, "
        "plugins ativos e política gerenciada), não do período. \"Com motivo\" é "
        "estimativa: conta itens com `Motivo:`, `porque`, `para evitar` e afins, e "
        "erra nos dois sentidos. O tamanho em tokens usa o mesmo fator do peso fixo.")]
    return lines


def _cost(a: Audit) -> list[str]:
    c = a.cost
    lines = ["## Custo", "",
              f"- Total: {n(c.total.total)} tokens; subagentes {n(c.total.subagents)} "
              f"({pct(c.total.subagents, c.total.total)})",
              f"- Por sessão: {_summary(c.session_summary)}",
              f"- Por pedido: {_summary(c.prompt_summary)} ({n(c.prompt_summary.n)} pedidos)",
              f"- Sem pedido atribuído: {n(c.without_prompt)} tokens da sessão principal"]
    if a.costly:
        lines += ["", f"Os {len(a.costly)} pedidos mais caros:", "",
                   "| Início do pedido | Tokens | Subagentes |", "|---|---:|---:|"]
        for p in a.costly:
            lines.append(f"| {when(p.start)} | {n(p.spend.total)} | "
                          f"{pct(p.spend.subagents, p.spend.total)} |")
    lines += ["", how_to_read(
        "soma de entrada, saída e cache (criado e lido), uma vez por resposta "
        "(E4). Cache lido entra com o mesmo peso: o número mede volume, não "
        "dinheiro. Trabalho disparado por aviso de tarefa em segundo plano entra "
        "no pedido humano anterior (E9).")]
    return lines


def _interventions(a: Audit) -> list[str]:
    it = a.interventions
    t = it.total
    with_signal = sum(1 for x in it.by_prompt.values() if x.signals)
    modes = sorted(it.by_mode.items(), key=lambda kv: (-kv[1], kv[0]))
    lines = ["## Intervenções", "",
              f"- Pedidos humanos: {n(t.prompts)} em {n(a.sessions)} sessões "
              f"(por sessão: {_summary(it.prompts_summary)})",
              f"- Interrupções: {n(t.interruptions)} · rejeições de ferramenta: "
              f"{n(t.rejections)} ({n(t.rejections_with_comment)} com comentário) · "
              f"mensagens no meio do turno: {n(t.mid_turn_messages)}",
              f"- Pedidos com algum sinal: {n(with_signal)} de {n(t.prompts)} · sessões "
              f"sem nenhum sinal: {n(it.sessions_without_signal)} de {n(a.sessions)}",
              "- Modo de permissão dos pedidos: " + (", ".join(
                  f"`{m}` {n(k)}" for m, k in modes) or "—"),
              "", "Avisos:", ""]
    without_rejection = a.prompts_without_rejection
    lines += [
        "- São contagens cruas, ao lado do número de pedidos. Com tão poucos "
        "eventos, nenhuma taxa ou ordenação de sessões tem sentido.",
        f"- Nos modos {code(MODES_WITHOUT_REJECTION)} o usuário não é consultado, e a "
        f"rejeição de ferramenta não tem como aparecer: {n(without_rejection)} de "
        f"{n(t.prompts)} pedidos rodaram assim.",
        "- Atenção: a ausência de sinais não indica ausência de correções. A "
        "correção digitada depois que o turno acaba é só mais um pedido.",
        "- \"Pedidos por tarefa\", a medida mais promissora, ainda não existe: o "
        "critério que agrupa pedidos em tarefa está em aberto (E9).",
        "", how_to_read(
            "interrupção e mensagem no meio do turno medem também o hábito de "
            "acompanhar o agente enquanto ele trabalha, não só como ele se saiu.")]
    return lines


def _hooks(a: Audit) -> list[str]:
    h = a.hooks
    lines = ["## Hooks", ""]
    if not h.total:
        lines.append("Nenhum desfecho visível de hook no período.")
    else:
        lines += [f"Desfechos visíveis: {n(h.total)}, em {n(h.sessions_with_hook)} sessões "
                   f"({n(h.in_subagents)} em subagentes); bloqueios: {n(h.blocks_count)}.",
                   "", "| Evento | Desfechos visíveis | Por tipo |", "|---|---:|---|"]
        for event, total in sorted(h.by_event.items(), key=lambda kv: (-kv[1], kv[0])):
            kinds = sorted(((t, k) for (t, e), k in h.by_type_and_event.items()
                            if e == event), key=lambda tk: (-tk[1], tk[0]))
            detail = ", ".join(f"{HOOK_TYPES.get(t, t)} {n(k)}" for t, k in kinds)
            lines.append(f"| `{event}` | {n(total)} | {detail} |")
    lines += ["", how_to_read(
        "só aparece o que o hook deixou visível: saída, falha, bloqueio, tempo "
        "esgotado. Hook que roda bem e calado não deixa registro, então zero "
        "desfechos visíveis não quer dizer que o hook não roda (E6). Evento `?` é "
        "registro que não diz o evento.")]
    return lines


def _commits(a: Audit) -> list[str]:
    c = a.commits
    lines = ["## Commits", ""]
    if not c.calls:
        lines.append("Nenhuma chamada de `git commit` no período.")
    else:
        lines += [
            f"- Chamadas de `git commit`: {n(c.calls)}, em {n(c.sessions_with_commit)} "
            f"sessões ({n(c.in_subagents)} em subagentes)",
            f"- Com hash registrado: {n(c.with_hash)} · sem hash: {n(c.without_hash)}",
            f"- Silenciosas (`-q` ou `--quiet`): {n(c.silent)} · amends: "
            f"{n(c.amends)} · com erro: {n(c.with_error)}"]
        if c.approximate_count:
            lines.append(f"- Detectadas por padrão, sem análise do comando: "
                          f"{n(c.approximate_count)}")
        lines += _commit_linking(a)
        if c.silent:
            lines += [
                "", "Efeito das chamadas silenciosas: com `-q` o git não imprime o "
                "hash, e a transcrição não o registra. A ligação da sessão ao commit "
                "passa a depender da janela de horário (E7), que pode ser ambígua e "
                "se perde quando a branch é apagada.",
                "", "Regra que resolve, para o `CLAUDE.md` do repositório: "
                "\"Faça `git commit` sem `-q`.\""]
    lines += ["", how_to_read(
        "conta comandos `git commit` analisados, incluindo os de subagentes; "
        "dentro de `bash -c` ou `eval` não aparecem. Sem hash registrado não quer "
        "dizer que o commit não existe, só que a transcrição não diz qual foi. A "
        "ligação pela janela usa o repositório do diretório da chamada (E3): "
        "comando que faz `cd` para outro repositório fica sem ligação. O amend é "
        "o do comando; quando o commit foi ligado, o histórico git decide (E7).")]
    return lines


def _commit_linking(a: Audit) -> list[str]:
    if a.no_git:
        return ["- Ligação aos commits do repositório: consulta ao git pulada (`--sem-git`)."]
    links = a.commit_linking
    if links is None:
        return []
    f = links.by_form()
    lines = [f"- Ligação aos commits: com hash: {n(f['hash'])} · ligadas por janela: "
              f"{n(f['window'])} · ambíguas: {n(f['ambiguous'])} · sem ligação: "
              f"{n(f['unlinked'])}"]
    reasons = links.unlinked_by_reason()
    if reasons:
        lines.append("  - sem ligação, por motivo: " + ", ".join(
            f"{m} {n(k)}" for m, k in sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))))
    lines.append(f"- Amends: {n(links.amends)} (pelo comando: {n(links.amends_by_command)}; "
                  f"o git confirmou {n(links.amends_confirmed)} e não confirmou "
                  f"{n(links.amends_unconfirmed)}; achados só pelo git: "
                  f"{n(links.amends_only_by_git)})")
    if links.amends_kind:
        lines.append(f"  - o `kind` gravado pelo Claude Code diz amend em "
                      f"{n(links.amends_kind)}; guardado à parte, não entra na conta "
                      f"(dá falso positivo com `--amend` dentro de heredoc)")
    linked = links.linked_commits
    lines.append(f"- Dos {n(len(linked))} commits ligados: revertidos depois: "
                  f"{n(len(links.reverted))} · refeitos por amend depois: "
                  f"{n(len(links.replaced_commits))}")
    return lines


def _appendix(a: Audit) -> list[str]:
    lines = ["## Apêndice", ""]
    empty = True
    for key, title in CATEGORIES.items():
        c: ind.Category = getattr(a.dead_weight, key)
        if not c.never_used:
            continue
        empty = False
        lines += [f"### {title} nunca usados ({n(len(c.never_used))})", ""]
        for name in sorted(c.never_used):
            o = a.provenance(key, name)
            if o is None:
                lines.append(f"- `{name}`")
            else:
                path = f" — `{o.path}`" if o.path else ""
                lines.append(f"- `{name}` ({PROVENANCE_NAMES[o.provenance]}){path}")
        lines.append("")
    if a.not_announced:
        items = [*a.not_announced["skills"], *a.not_announced["subagent_types"]]
        if items:
            empty = False
            lines += [f"### Instalados e não anunciados ({n(len(items))})", ""]
            lines += [f"- `{p.name}` ({p.kind}, {PROVENANCE_NAMES[p.scope]}) — `{p.source}`"
                       for p in items]
            lines.append("")
    if a.unknowns.kinds or a.unknowns.fields:
        empty = False
        lines += ["### Formato desconhecido", ""]
        for name, qty in sorted(a.unknowns.kinds.items()):
            lines.append(f"- tipo `{name}`: {n(qty)}")
        for name, qty in sorted(a.unknowns.fields.items()):
            lines.append(f"- campo `{name}`: {n(qty)}")
        lines.append("")
    if empty:
        lines += ["Nada a detalhar.", ""]
    lines.append(how_to_read(
        "listas completas do que o corpo resume. Formato desconhecido interessa a quem "
        "mantém o leitor: tipos e campos que o leitor contou e não interpretou (E1)."))
    return lines


def markdown(a: Audit) -> str:
    parts = [_header(a)]
    if a.sessions:
        parts += [_attention(a), _fixed_context(a), _dead_weight(a)]
        if a.installed is not None:
            parts.append(_installed(a))
        parts += [_cost(a), _interventions(a), _hooks(a), _commits(a), _appendix(a)]
    return "\n\n".join("\n".join(p) for p in parts) + "\n"
