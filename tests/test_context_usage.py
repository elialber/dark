"""Tests for the context breakdown (`/context` in non-interactive mode).

The samples in tests/fixtures/context/ have the structure of the real output of
Claude Code 2.1.326, with made-up names. No test calls Claude Code:
the executor is injected.
"""

from pathlib import Path

import pytest

from dark import context_usage

SAMPLES = Path(__file__).parent / "fixtures" / "context"


def read(name: str) -> str:
    return (SAMPLES / name).read_text(encoding="utf-8")


def parse(name: str) -> context_usage.Breakdown:
    return context_usage.parse(read(name))


# --- numbers ---------------------------------------------------------------

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
def test_number_with_separator_and_suffix(text, expected):
    assert context_usage.number(text) == expected


@pytest.mark.parametrize("text", ["", "muitos", "1.2.3", "k", "12x", "-5"])
def test_invalid_number_returns_none(text):
    assert context_usage.number(text) is None


# --- complete output ---------------------------------------------------------

def test_complete_header():
    r = parse("complete.md")
    assert r.model == "modelo-exemplo"
    assert r.total == 10900
    assert r.window == 200_000


def test_complete_categories_and_kinds():
    r = parse("complete.md")
    by_name = {c.name: c for c in r.categories}
    assert list(by_name) == [
        "System prompt", "System tools", "MCP tools (deferred)",
        "System tools (deferred)", "Custom agents", "Memory files", "Skills",
        "Messages", "Free space", "Autocompact buffer",
    ]
    assert by_name["System prompt"].tokens == 2500
    assert by_name["System prompt"].kind == "used"
    assert by_name["MCP tools (deferred)"].kind == "deferred"
    assert by_name["System tools (deferred)"].kind == "deferred"
    assert by_name["Free space"].kind == "free"
    assert by_name["Autocompact buffer"].kind == "reserved"
    assert all(c.known for c in r.categories)


def test_complete_categories_sum_against_total():
    r = parse("complete.md")
    # 2500 + 5700 + 40 + 319 + 2300 + 10: only those that count in the total
    assert r.categories_sum == 10869
    assert r.total - r.categories_sum == 31          # rounding in the text


def test_complete_deferred_tools_outside_the_total():
    r = parse("complete.md")
    assert r.deferred == 16300 + 120


def test_complete_skills_with_provenance():
    r = parse("complete.md")
    assert [(s.name, s.source, s.tokens) for s in r.skills] == [
        ("exemplo-skill", "User", 220),
        ("outra-skill", "Project", 1200),
        ("ferramenta:exemplo-plugin", "Plugin (exemplo-plugin)", 90),
        ("skill-embutida", "Built-in", 480),
        ("skill-sincronizada", "claude.ai sync", 340),
    ]


def test_complete_mcp_agents_and_memory():
    r = parse("complete.md")
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


def test_complete_nothing_left_unrecognized():
    assert parse("complete.md").unrecognized == []


# --- variations --------------------------------------------------------------

def test_no_skills():
    r = parse("no-skills.md")
    assert r.skills == [] and r.mcp_tools == [] and r.agents == []
    assert r.total == 8200 and r.categories_sum == 8210
    assert r.deferred == 16300
    assert r.unrecognized == []


def test_numbers_with_separator_and_suffix_in_output():
    r = parse("numbers.md")
    assert r.total == 1_200_000 and r.window == 2_000_000
    by_name = {c.name: c.tokens for c in r.categories}
    assert by_name["System prompt"] == 1234
    assert by_name["Messages"] == 1_180_000
    assert by_name["Free space"] == 767_000
    assert by_name["Autocompact buffer"] == 33_000
    assert [s.tokens for s in r.skills] == [1500, 500]
    assert r.deferred == 0
    assert r.unrecognized == []


def test_unknown_section_and_lines_are_kept_and_do_not_break():
    r = parse("unknown-section.md")
    assert r.total == 8300
    # a new category goes in (counts in the total) but is flagged and reported
    new_category = [c for c in r.categories if c.name == "Output styles"]
    assert len(new_category) == 1 and not new_category[0].known and new_category[0].kind == "used"
    assert r.categories_sum == 8300
    texts = "\n".join(r.unrecognized)
    assert "Output styles" in texts                 # unknown category
    assert "**Cache:**" in texts                    # new header line
    assert "### Hooks" in texts                     # new section
    assert "hook-exemplo" in texts                  # lines of the new section
    assert "muitos" in texts                        # unreadable number
    assert "Linha solta no fim." in texts
    assert r.skills == []                            # the unreadable line does not become a skill


def test_empty_output_is_error():
    with pytest.raises(context_usage.InvalidOutput):
        parse("empty.md")


def test_output_without_category_is_error():
    with pytest.raises(context_usage.InvalidOutput):
        parse("no-categories.md")


def test_parse_does_not_depend_on_line_endings():
    text = read("complete.md").replace("\n", "\r\n")
    assert context_usage.parse(text) == parse("complete.md")


# --- unattributed part -------------------------------------------------------

def test_unattributed_against_usage():
    r = parse("complete.md")
    unattr = context_usage.unattributed(r, 16350)
    assert unattr.measured == 16350 and unattr.given == 10900
    assert unattr.tokens == 5450
    assert unattr.percent == pytest.approx(33.333, abs=0.001)


def test_unattributed_negative_when_usage_is_smaller():
    unattr = context_usage.unattributed(parse("complete.md"), 10000)
    assert unattr.tokens == -900
    assert unattr.percent == pytest.approx(-9.0)


def test_unattributed_rejects_invalid_usage():
    with pytest.raises(ValueError):
        context_usage.unattributed(parse("complete.md"), 0)


# --- execution ---------------------------------------------------------------

def test_execute_uses_injected_executor(tmp_path):
    calls = []

    def executor(arguments, directory):
        calls.append((arguments, directory))
        return read("complete.md")

    text = context_usage.execute(tmp_path, executor=executor)
    assert text == read("complete.md")
    [(arguments, directory)] = calls
    assert directory == tmp_path
    assert arguments[:3] == ["claude", "-p", "/context"]
    # leaves no transcript in the user's directory
    assert "--no-session-persistence" in arguments


def test_execute_rejects_nonexistent_directory(tmp_path):
    with pytest.raises(FileNotFoundError):
        context_usage.execute(tmp_path / "missing", executor=lambda a, d: "")


def test_measure_combines_execution_and_parsing(tmp_path):
    r = context_usage.measure(tmp_path, executor=lambda a, d: read("no-skills.md"))
    assert r.total == 8200
