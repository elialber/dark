"""Testes da repartição do contexto (`/context` em modo não interativo).

As amostras de tests/fixtures/contexto/ têm a estrutura da saída real do
Claude Code 2.1.326, com nomes inventados. Nenhum teste chama o Claude Code:
o executor é injetado.
"""

from pathlib import Path

import pytest

from dark import context_usage

SAMPLES = Path(__file__).parent / "fixtures" / "contexto"


def read(name: str) -> str:
    return (SAMPLES / name).read_text(encoding="utf-8")


def parse(name: str) -> context_usage.Breakdown:
    return context_usage.parse(read(name))


# --- números ---------------------------------------------------------------

@pytest.mark.parametrize("text, expected", [
    ("319", 319),
    ("10", 10),
    ("1,234", 1234),
    ("767,000", 767000),
    ("2.5k", 2500),
    ("12.3k", 12300),
    ("33k", 33000),
    ("33K", 33000),
    ("~220", 220),
    ("~1.2k", 1200),
    ("~1,500", 1500),
    ("~0.5k", 500),
    ("1m", 1_000_000),
    ("1.18m", 1_180_000),
    (" 59 ", 59),
])
def test_numero_com_separador_e_sufixo(text, expected):
    assert context_usage.number(text) == expected


@pytest.mark.parametrize("text", ["", "muitos", "1.2.3", "k", "12x", "-5"])
def test_numero_invalido_devolve_none(text):
    assert context_usage.number(text) is None


# --- saída completa ----------------------------------------------------------

def test_completa_cabecalho():
    r = parse("completa.md")
    assert r.model == "modelo-exemplo"
    assert r.total == 10900
    assert r.window == 200_000


def test_completa_categorias_e_tipos():
    r = parse("completa.md")
    by_name = {c.name: c for c in r.categories}
    assert list(by_name) == [
        "System prompt", "System tools", "MCP tools (deferred)",
        "System tools (deferred)", "Custom agents", "Memory files", "Skills",
        "Messages", "Free space", "Autocompact buffer",
    ]
    assert by_name["System prompt"].tokens == 2500
    assert by_name["System prompt"].kind == "usado"
    assert by_name["MCP tools (deferred)"].kind == "adiado"
    assert by_name["System tools (deferred)"].kind == "adiado"
    assert by_name["Free space"].kind == "livre"
    assert by_name["Autocompact buffer"].kind == "reserva"
    assert all(c.known for c in r.categories)


def test_completa_soma_das_categorias_contra_total():
    r = parse("completa.md")
    # 2500 + 5700 + 40 + 319 + 2300 + 10: só as que contam no total
    assert r.categories_sum == 10869
    assert r.total - r.categories_sum == 31          # arredondamento do texto


def test_completa_ferramentas_adiadas_fora_do_total():
    r = parse("completa.md")
    assert r.deferred == 16300 + 120


def test_completa_skills_com_origem():
    r = parse("completa.md")
    assert [(s.name, s.source, s.tokens) for s in r.skills] == [
        ("exemplo-skill", "User", 220),
        ("outra-skill", "Project", 1200),
        ("ferramenta:exemplo-plugin", "Plugin (exemplo-plugin)", 90),
        ("skill-embutida", "Built-in", 480),
        ("skill-sincronizada", "claude.ai sync", 340),
    ]


def test_completa_mcp_agentes_e_memoria():
    r = parse("completa.md")
    assert [(f.name, f.source, f.tokens) for f in r.mcp_tools] == [
        ("mcp__servidor-a__ferramenta_um", "servidor-a", 59),
        ("mcp__servidor-b__ferramenta_dois", "servidor-b", 61),
    ]
    assert [(a.name, a.source, a.tokens) for a in r.agents] == [
        ("agente-exemplo", "Project", 20),
        ("outro-agente", "User", 20),
    ]
    assert [(m.name, m.source, m.tokens) for m in r.memory] == [
        ("/repo/exemplo/CLAUDE.md", "Project", 300),
        ("/home/exemplo/.claude/CLAUDE.md", "User", 19),
    ]


def test_completa_nada_fica_sem_reconhecer():
    assert parse("completa.md").unrecognized == []


# --- variações ---------------------------------------------------------------

def test_sem_skills():
    r = parse("sem-skills.md")
    assert r.skills == [] and r.mcp_tools == [] and r.agents == []
    assert r.total == 8200 and r.categories_sum == 8210
    assert r.deferred == 16300
    assert r.unrecognized == []


def test_numeros_com_separador_e_sufixo_na_saida():
    r = parse("numeros.md")
    assert r.total == 1_200_000 and r.window == 2_000_000
    by_name = {c.name: c.tokens for c in r.categories}
    assert by_name["System prompt"] == 1234
    assert by_name["Messages"] == 1_180_000
    assert by_name["Free space"] == 767_000
    assert by_name["Autocompact buffer"] == 33_000
    assert [s.tokens for s in r.skills] == [1500, 500]
    assert r.deferred == 0
    assert r.unrecognized == []


def test_secao_e_linhas_desconhecidas_sao_guardadas_e_nao_derrubam():
    r = parse("secao-desconhecida.md")
    assert r.total == 8300
    # categoria nova entra (conta no total) mas é marcada e relatada
    new_category = [c for c in r.categories if c.name == "Output styles"]
    assert len(new_category) == 1 and not new_category[0].known and new_category[0].kind == "usado"
    assert r.categories_sum == 8300
    texts = "\n".join(r.unrecognized)
    assert "Output styles" in texts                 # categoria desconhecida
    assert "**Cache:**" in texts                    # linha de cabeçalho nova
    assert "### Hooks" in texts                     # seção nova
    assert "hook-exemplo" in texts                  # linhas da seção nova
    assert "muitos" in texts                        # número ilegível
    assert "Linha solta no fim." in texts
    assert r.skills == []                            # a linha ilegível não vira skill


def test_saida_vazia_e_erro():
    with pytest.raises(context_usage.InvalidOutput):
        parse("vazia.md")


def test_saida_sem_categoria_e_erro():
    with pytest.raises(context_usage.InvalidOutput):
        parse("sem-categorias.md")


def test_analisar_nao_depende_de_fim_de_linha():
    text = read("completa.md").replace("\n", "\r\n")
    assert context_usage.parse(text) == parse("completa.md")


# --- parte não atribuída -----------------------------------------------------

def test_nao_atribuido_contra_usage():
    r = parse("completa.md")
    unattr = context_usage.unattributed(r, 16350)
    assert unattr.measured == 16350 and unattr.given == 10900
    assert unattr.tokens == 5450
    assert unattr.percent == pytest.approx(33.333, abs=0.001)


def test_nao_atribuido_negativo_quando_usage_e_menor():
    unattr = context_usage.unattributed(parse("completa.md"), 10000)
    assert unattr.tokens == -900
    assert unattr.percent == pytest.approx(-9.0)


def test_nao_atribuido_rejeita_usage_invalido():
    with pytest.raises(ValueError):
        context_usage.unattributed(parse("completa.md"), 0)


# --- execução ----------------------------------------------------------------

def test_executar_usa_executor_injetado(tmp_path):
    calls = []

    def executor(arguments, directory):
        calls.append((arguments, directory))
        return read("completa.md")

    text = context_usage.execute(tmp_path, executor=executor)
    assert text == read("completa.md")
    [(arguments, directory)] = calls
    assert directory == tmp_path
    assert arguments[:3] == ["claude", "-p", "/context"]
    # não deixa transcrição no diretório do usuário
    assert "--no-session-persistence" in arguments


def test_executar_rejeita_diretorio_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError):
        context_usage.execute(tmp_path / "nao-existe", executor=lambda a, d: "")


def test_medir_junta_execucao_e_analise(tmp_path):
    r = context_usage.measure(tmp_path, executor=lambda a, d: read("sem-skills.md"))
    assert r.total == 8200
