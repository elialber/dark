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
SUBCOMMANDS = ("auditar", "coletar", "iniciar", "adicionar", "verificar", "remover")

_FENCE = re.compile(r"^```.*?^```", re.DOTALL | re.MULTILINE)
_SPAN = re.compile(r"`([^`\n]+)`")
_DARK_COMMAND = re.compile(r"(?:^|\s)(?:python -m )?dark( [^\s`|]+)?((?: [^\n`|]*)?)")
_OPTION = re.compile(r"(?<![\w-])--[a-z][a-z-]*")
_RULE_ID = re.compile(r"[a-z]+(?:_[a-z0-9]+)+")
_CONSTANT = re.compile(r"[A-Z]+(?:_[A-Z0-9]+)+")
_ABLATION_CONSTANTS = ("TOLERANCE_RUNS", "TOLERANCE_BASE", "MIN_RUNS")  # checked against ablation.py below
_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_THRESHOLD_ROW = re.compile(r"^\|\s*`((?!TOLERANCE_|MIN_RUNS)[A-Z0-9_]+)`\s*\|\s*(\d+)\b", re.MULTILINE)


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
    union = set().union(*known.values()) | _evals_help_options("ablacao", capsys)
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
        if _CONSTANT.fullmatch(piece) and not hasattr(recommend, piece) \
                and piece not in _ABLATION_CONSTANTS:
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
    assert names == {"UNUSED_WEEKS", "INSTRUCTION_LINES_CEILING", "HOOK_BLOCKS_MIN",
                     "EVALS_ROUNDS_AT_100"}


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


# ---------------------------------------------------------------------------
# Ablation (goal 037): `python -m dark.evals ablacao` in docs/metodo.md and README.md
# ---------------------------------------------------------------------------

README = ROOT / "README.md"
_EVALS_COMMAND = re.compile(r"python -m dark\.evals ([a-z]+)((?:[^\n`]|\\\n)*)")
_OUTCOME_SPAN = re.compile(r"`((?:pode remover|mantenha|inconclusivo|não discrimina))`")
_NUMBER_ROW = re.compile(r"^\|\s*`(TOLERANCE_RUNS|TOLERANCE_BASE|MIN_RUNS)`\s*\|\s*(\d+)\b",
                         re.MULTILINE)


def _evals_help_options(sub: str, capsys) -> set[str]:
    from dark.evals import __main__ as evals_main
    capsys.readouterr()
    try:
        evals_main.main([sub, "--help"])
    except SystemExit:
        pass
    return set(_OPTION.findall(capsys.readouterr().out))


def evals_option_problems(text: str, capsys) -> list[str]:
    """Every `--opt` next to `python -m dark.evals <sub>` exists in that subcommand's --help."""
    problems = []
    cache: dict[str, set[str]] = {}
    for sub, rest in _EVALS_COMMAND.findall(text):
        if sub not in cache:
            cache[sub] = _evals_help_options(sub, capsys)
        if not cache[sub]:
            problems.append(f"`python -m dark.evals {sub}` is not a subcommand")
            continue
        for option in _OPTION.findall(rest):
            if option not in cache[sub]:
                problems.append(f"{option} is not in `python -m dark.evals {sub} --help`")
    return problems


def outcome_problems(text: str) -> list[str]:
    from dark.evals import ablation
    real = set(ablation.OUTCOME_LABELS.values())
    problems = [f"`{label}` is not in OUTCOME_LABELS" for label in _OUTCOME_SPAN.findall(text)
                if label not in real]
    # An outcome-shaped span after "saída"/"Ablação:" that is not real.
    for label in re.findall(r"Ablação: ([^\n]+)", text):
        if label.strip() not in real:
            problems.append(f"`{label.strip()}` is not in OUTCOME_LABELS")
    return problems


def number_problems(text: str) -> list[str]:
    from dark.evals import ablation
    problems = []
    for name, value in _NUMBER_ROW.findall(text):
        if getattr(ablation, name, None) != int(value):
            problems.append(f"{name} is {getattr(ablation, name, None)}, the text says {value}")
    return problems


def test_the_method_doc_cites_the_four_outcomes_and_the_numbers():
    from dark.evals import ablation
    text = _doc()
    for label in ablation.OUTCOME_LABELS.values():
        assert f"`{label}`" in text, label
    assert {name for name, _ in _NUMBER_ROW.findall(text)} \
        == {"TOLERANCE_RUNS", "TOLERANCE_BASE", "MIN_RUNS"}


def test_every_evals_option_cited_in_the_docs_exists_in_help(capsys):
    for path in (DOC, README):
        assert evals_option_problems(path.read_text(encoding="utf-8"), capsys) == [], path.name


def test_the_ablation_outcomes_cited_exist():
    for path in (DOC, README):
        assert outcome_problems(path.read_text(encoding="utf-8")) == [], path.name


def test_the_ablation_numbers_cited_match_the_constants():
    assert number_problems(_doc()) == []


def test_the_readme_mentions_the_ablation_command_and_links_the_method():
    text = README.read_text(encoding="utf-8")
    assert "python -m dark.evals ablacao" in text
    assert "docs/metodo.md" in text


def test_the_docs_cite_the_supported_and_refused_kinds():
    from dark.evals import ablation
    text = _doc()
    for kind in (*ablation.SUPPORTED_KINDS, *ablation.UNSUPPORTED_KINDS):
        assert f"`{kind}`" in text, kind


def test_probe_an_evals_option_that_does_not_exist_fails(capsys):
    assert evals_option_problems("`python -m dark.evals ablacao --inexistente`", capsys) \
        == ["--inexistente is not in `python -m dark.evals ablacao --help`"]
    assert evals_option_problems("```bash\npython -m dark.evals ablacao --tipo skill \\\n"
                                 "  --simular x.toml\n```", capsys) == []
    assert evals_option_problems("`python -m dark.evals banana --tipo x`", capsys) \
        == ["`python -m dark.evals banana` is not a subcommand"]


def test_probe_an_outcome_that_does_not_exist_fails():
    assert outcome_problems("a saída `pode remover`, `talvez`") == []
    assert outcome_problems("Ablação: talvez remover") == ["`talvez remover` is not in OUTCOME_LABELS"]
    assert outcome_problems("Ablação: pode remover") == []


def test_probe_a_wrong_ablation_number_fails():
    assert number_problems("| `MIN_RUNS` | 20 | x |") == ["MIN_RUNS is 15, the text says 20"]
    assert number_problems("| `TOLERANCE_RUNS` | 4 | x |") == []


# ---------------------------------------------------------------------------
# Goal 045: `iniciar`, `adicionar`, `verificar`, `remover`, `coletar --evals`
# and `python -m dark.evals guardar` in README.md and docs/metodo.md
# ---------------------------------------------------------------------------

def _readme_for_users() -> str:
    """README.md without "Desenvolvimento": that section cites developer-only commands
    (`python -m dark.reader --nomes`, ...) that are not in any `dark` --help."""
    text = README.read_text(encoding="utf-8")
    return text.split("\n## Desenvolvimento\n")[0]


def test_the_docs_cite_the_scaffold_commands_and_the_evals_import():
    readme = README.read_text(encoding="utf-8")
    for command in ("dark iniciar", "dark adicionar", "dark adicionar --listar", "dark verificar",
                    "dark remover", "dark coletar --evals", "python -m dark.evals guardar"):
        assert command in readme, command
    doc = _doc()
    for command in ("dark iniciar", "dark coletar --evals", "python -m dark.evals guardar"):
        assert command in doc, command


def test_every_command_and_option_cited_in_the_readme_exists_in_help(capsys):
    text = _readme_for_users()
    assert "## Preparar o repositório" in text
    assert command_problems(text, capsys) == []
    assert evals_option_problems(text, capsys) == []


def test_the_method_doc_cites_both_evals_rules_and_their_constant():
    text = _doc()
    for rule in ("evals_at_100_percent", "model_changed_since_last_evals"):
        assert f"| `{rule}` |" in text, rule
    assert "| `EVALS_ROUNDS_AT_100` | 3 rodadas |" in text
    assert recommend.EVALS_ROUNDS_AT_100 == 3
    # The deferred list in the text is exactly recommend.DEFERRED.
    assert set(recommend.DEFERRED) == {"third_party_module_without_gain"}
    assert "`model_changed_since_last_evals` e `third_party_module_without_gain`" not in text


def test_probe_options_of_the_scaffold_commands_that_do_not_exist_fail(capsys):
    for sub in ("iniciar", "adicionar", "verificar", "remover", "coletar"):
        assert command_problems(f"`dark {sub} --inexistente`", capsys) \
            == [f"--inexistente is not in `dark {sub} --help`"], sub
    assert command_problems("`dark verificar --aplicar`", capsys) \
        == ["--aplicar is not in `dark verificar --help`"]
    assert command_problems("`dark iniciar --aplicar`, `dark adicionar --listar`, "
                            "`dark remover base`, `dark coletar --evals x.jsonl`", capsys) == []
    assert evals_option_problems("`python -m dark.evals guardar --inexistente`", capsys) \
        == ["--inexistente is not in `python -m dark.evals guardar --help`"]
    assert evals_option_problems("`python -m dark.evals guardar x.jsonl --banco y`", capsys) == []


def test_probe_a_wrong_evals_rounds_value_fails():
    assert rule_problems("| `EVALS_ROUNDS_AT_100` | 5 rodadas | x |") \
        == ["EVALS_ROUNDS_AT_100 is 3, the text says 5"]
    assert rule_problems("`EVALS_ROUNDS_AT_9`") \
        == ["`EVALS_ROUNDS_AT_9` is not a constant of recommend.py"]
