"""Drift test for `docs/metodo.md` (goal 035).

The method document cites commands, options, rule identifiers, thresholds
and relative links. Each of them is checked against the real thing, so the
text cannot drift from the code. The checkers take the text as an argument so
the probes at the bottom can feed them a doctored copy.
"""

from __future__ import annotations

import re
from pathlib import Path

from dark import recommend

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "metodo.md"
SUBCOMMANDS = ("auditar", "coletar")

_FENCE = re.compile(r"^```.*?^```", re.DOTALL | re.MULTILINE)
_SPAN = re.compile(r"`([^`\n]+)`")
_DARK_COMMAND = re.compile(r"(?:^|\s)(?:python -m )?dark( [^\s`|]+)?((?: [^\n`|]*)?)")
_OPTION = re.compile(r"(?<![\w-])--[a-z][a-z-]*")
_RULE_ID = re.compile(r"[a-z]+(?:_[a-z0-9]+)+")
_CONSTANT = re.compile(r"[A-Z]+(?:_[A-Z]+)+")
_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_THRESHOLD_ROW = re.compile(r"^\|\s*`([A-Z_]+)`\s*\|\s*(\d+)\b", re.MULTILINE)


def _help(args: list[str], capsys) -> str:
    from dark import cli
    capsys.readouterr()
    try:
        cli.main([*args, "--help"])
    except SystemExit:
        pass
    return capsys.readouterr().out


def _help_options(args: list[str], capsys) -> set[str]:
    return set(_OPTION.findall(_help(args, capsys)))


def _code_pieces(text: str) -> list[str]:
    """Fenced blocks (line by line) and inline spans."""
    pieces = []
    for block in _FENCE.findall(text):
        pieces += block.splitlines()[1:-1]
    pieces += _SPAN.findall(_FENCE.sub("", text))
    return pieces


def command_problems(text: str, capsys) -> list[str]:
    """`dark <sub> ... --opt` pieces and bare `--opt` spans, against `--help`."""
    problems = []
    known = {"": _help_options([], capsys)}
    for sub in SUBCOMMANDS:
        known[sub] = _help_options([sub], capsys)
    union = set().union(*known.values())
    for piece in _code_pieces(text):
        piece = piece.strip()
        found = _DARK_COMMAND.search(piece)
        if found and not piece.startswith(("python -m dark.", "dark.")):
            first = (found.group(1) or "").strip()
            if first and not first.startswith("-"):
                if first not in SUBCOMMANDS:
                    problems.append(f"`dark {first}` is not a command")
                    continue
                allowed = known[first]
            else:
                allowed = known[""]
            rest = (found.group(1) or "") + (found.group(2) or "")
            for option in _OPTION.findall(rest):
                if option not in allowed:
                    problems.append(f"{option} is not in `dark {first} --help`".replace("  ", " "))
        elif re.fullmatch(r"--[a-z][a-z-]*(?: <[^>]+>| N)?", piece):
            option = piece.split()[0]
            if option not in union:
                problems.append(f"{option} is in no `dark` --help")
    return problems


def rule_problems(text: str) -> list[str]:
    real = {rule.__name__ for rule in recommend.RULES} | set(recommend.DEFERRED)
    problems = []
    for piece in _code_pieces(text):
        piece = piece.strip()
        if _RULE_ID.fullmatch(piece) and piece not in real:
            problems.append(f"`{piece}` is not a rule of recommend.py")
        if _CONSTANT.fullmatch(piece) and not hasattr(recommend, piece):
            problems.append(f"`{piece}` is not a constant of recommend.py")
    for name, value in _THRESHOLD_ROW.findall(text):
        if getattr(recommend, name, None) != int(value):
            problems.append(f"{name} is {getattr(recommend, name, None)}, the text says {value}")
    return problems


def link_problems(text: str, base: Path = DOC.parent) -> list[str]:
    problems = []
    for target in _LINK.findall(text):
        if re.match(r"[a-z]+:", target) or target.startswith("#"):
            continue
        if not (base / target.split("#")[0]).exists():
            problems.append(f"link to a file that does not exist: {target}")
    return problems


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def test_the_document_exists_and_cites_every_rule():
    text = _doc()
    for rule in recommend.RULES:
        assert f"`{rule.__name__}`" in text, rule.__name__


def test_every_dark_command_and_option_cited_exists_in_help(capsys):
    assert command_problems(_doc(), capsys) == []


def test_the_document_cites_the_commands_it_teaches(capsys):
    text = _doc()
    assert "dark auditar" in text and "dark coletar" in text
    assert "--todos" in text


def test_every_rule_and_constant_cited_exists_in_recommend():
    assert rule_problems(_doc()) == []


def test_the_thresholds_table_covers_every_threshold():
    names = {name for name, _ in _THRESHOLD_ROW.findall(_doc())}
    assert names == {"UNUSED_WEEKS", "INSTRUCTION_LINES_CEILING", "HOOK_BLOCKS_MIN"}


def test_every_relative_link_points_to_an_existing_file():
    assert link_problems(_doc()) == []


def test_the_document_has_no_personal_path_or_secret():
    text = _doc()
    for pattern in (r"/Users/[A-Za-z0-9._-]+", r"/home/[A-Za-z0-9._-]+",
                    r"sk-ant-[A-Za-z0-9_-]{8,}", r"github\.com[:/][A-Za-z0-9-]+/"):
        assert re.search(pattern, text) is None, pattern


# Probes: the checkers must fail on a doctored text.

def test_probe_an_option_that_does_not_exist_fails(capsys):
    assert command_problems("Rode `dark auditar --inexistente`.", capsys) \
        == ["--inexistente is not in `dark auditar --help`"]
    assert command_problems("Use `--inexistente`.", capsys) == ["--inexistente is in no `dark` --help"]


def test_probe_an_option_of_another_command_fails(capsys):
    assert command_problems("`dark coletar --dias 3`", capsys) \
        == ["--dias is not in `dark coletar --help`"]


def test_probe_a_command_that_does_not_exist_fails(capsys):
    assert command_problems("```bash\ndark painel\n```", capsys) == ["`dark painel` is not a command"]


def test_probe_real_commands_pass(capsys):
    assert command_problems("`dark auditar --todos --saida x`, `dark --versao`, `dark coletar`", capsys) == []


def test_probe_a_rule_that_does_not_exist_fails():
    assert rule_problems("a regra `regra_que_nao_existe`") \
        == ["`regra_que_nao_existe` is not a rule of recommend.py"]
    assert rule_problems("`commits_without_hash` e `evals_at_100_percent`") == []


def test_probe_a_wrong_threshold_fails():
    assert rule_problems("| `UNUSED_WEEKS` | 9 | x |") == ["UNUSED_WEEKS is 4, the text says 9"]


def test_probe_a_broken_link_fails():
    assert link_problems("[x](nao-existe.md) [y](decisoes.md#e1) [z](https://exemplo.org)") \
        == ["link to a file that does not exist: nao-existe.md"]
