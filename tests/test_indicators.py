"""Tests for the indicators.

The indicators are pure functions over the internal model. Here the sessions
come from the synthetic files in tests/fixtures/, read by the reader.
"""

from pathlib import Path

import pytest

from dark import indicators, reader

CONFIG = Path(__file__).parent / "fixtures" / "config"
S1 = "aaaaaaaa-0000-4000-8000-000000000001"
S4 = "aaaaaaaa-0000-4000-8000-000000000004"
S5 = "aaaaaaaa-0000-4000-8000-000000000005"
S6 = "aaaaaaaa-0000-4000-8000-000000000006"


@pytest.fixture(scope="module")
def sessions():
    return reader.read_all(CONFIG).sessions


def test_summary_of_empty_list_does_not_invent_a_number():
    r = indicators.summarize([])
    assert (r.n, r.median, r.minimum, r.maximum) == (0, None, None, None)
    assert indicators.summarize([3, 1, 2]).median == 2


# --- fixed context -------------------------------------------------------------

def test_fixed_context_per_session_and_summary(sessions):
    fc = indicators.fixed_context(sessions)
    assert fc.by_session[S6] == 32100
    assert fc.by_session[S1] == 80
    assert S4 not in fc.by_session and fc.without_data == [S4]     # fork
    assert (fc.summary.n, fc.summary.minimum, fc.summary.maximum) == (4, 1, 32100)
    assert fc.summary.median == 60                              # between 40 and 80


# --- dead weight ---------------------------------------------------------------

def test_dead_weight_of_skills(sessions):
    dw = indicators.dead_weight(sessions).skills
    assert dw.available == {"exemplo-skill", "outra-skill", "nunca-usada", "por-comando"}
    # by call, by attribution and by /command
    assert dw.used == {"exemplo-skill", "outra-skill", "por-comando"}
    assert dw.never_used == {"nunca-usada"}
    assert dw.used_outside_list == set()


def test_dead_weight_of_subagent_types(sessions):
    dw = indicators.dead_weight(sessions).subagent_types
    assert dw.used == {"exemplo-revisor"}
    assert dw.never_used == {"exemplo-ocioso", "Explore"}


def test_dead_weight_of_tools_and_servers(sessions):
    dw = indicators.dead_weight(sessions)
    assert dw.tools.never_used == {
        "WebFetch", "mcp__servidor-b__listar", "mcp__servidor-a__criar"}
    assert dw.tools.used_outside_list == {"Edit"}   # used without being in a list
    assert dw.mcp_servers.available == {"servidor-a", "servidor-b"}
    assert dw.mcp_servers.used == {"servidor-a"}
    assert dw.mcp_servers.never_used == {"servidor-b"}


def test_dead_weight_per_session_counts_available_and_used(sessions):
    dw = indicators.dead_weight(sessions)
    s6 = dw.skills.by_session[S6]
    assert (s6.available, s6.used) == (4, 3)
    assert dw.skills.by_session[S1].available == 0
    assert dw.skills.available_summary.maximum == 4
    assert dw.tools.by_session[S1].used == 5      # includes the subagent one (Read)
    assert dw.skills.sessions_without_list == 4


# --- interventions -------------------------------------------------------------

def test_interventions_per_session(sessions):
    it = indicators.interventions(sessions)
    s1 = it.by_session[S1]
    assert (s1.prompts, s1.interruptions, s1.rejections, s1.mid_turn_messages) == (2, 1, 1, 1)
    assert (s1.rejections_with_comment, s1.rejections_without_comment) == (1, 0)
    assert it.total.prompts == 7
    assert (it.total.interruptions, it.total.rejections, it.total.mid_turn_messages) == (1, 1, 1)
    assert it.sessions_without_signal == 4
    assert it.prompts_summary.maximum == 2


def test_interventions_per_prompt(sessions):
    it = indicators.interventions(sessions)
    p2 = it.by_prompt[(S1, "P2")]
    assert (p2.interruptions, p2.rejections, p2.mid_turn_messages) == (1, 1, 0)
    assert it.by_prompt[(S1, "P1")].mid_turn_messages == 1
    assert it.by_prompt[(S6, "PI1")].signals == 0


# --- cost ----------------------------------------------------------------------

def test_cost_per_session_with_subagent_share(sessions):
    c = indicators.cost(sessions)
    s1 = c.by_session[S1]
    assert (s1.main, s1.subagents, s1.total) == (138, 60, 198)
    assert s1.subagent_share == pytest.approx(60 / 198)
    assert c.total.total == 32432
    assert c.total.subagent_share == pytest.approx(60 / 32432)
    assert c.session_summary.maximum == 32119


def test_cost_per_prompt_adds_the_prompt_subagents(sessions):
    c = indicators.cost(sessions)
    p1 = c.by_prompt[(S1, "P1")]
    assert (p1.main, p1.subagents, p1.total) == (127, 60, 187)
    assert c.by_prompt[(S1, "P2")].total == 11
    assert c.prompt_summary.n == 7


# --- hooks ---------------------------------------------------------------------

def test_hooks_by_kind_and_by_event(sessions):
    h = indicators.hooks(sessions)
    assert h.by_type == {"success": 1, "non_blocking_error": 1, "cancelled": 2,
                          "block": 1, "stop": 1, "confirmation": 1, "decision": 1}
    assert h.by_event == {"SessionStart": 1, "PreToolUse": 6, "Stop": 1}
    assert h.by_type_and_event[("cancelled", "PreToolUse")] == 2
    assert h.in_subagents == 1
    assert h.blocks_count == 1
    assert h.total == 8


# --- commits -------------------------------------------------------------------

def test_commits_with_hash_without_hash_and_amends(sessions):
    c = indicators.commits(sessions)
    assert (c.calls, c.with_hash, c.without_hash, c.amends, c.silent) == (3, 2, 1, 1, 1)
    assert c.sessions_with_commit == 1
    assert c.by_session[S6].calls == 3
    assert c.approximate_count == 0


def test_indicators_do_not_change_the_sessions(sessions):
    before = [(s.id, len(s.responses), s.tokens.total) for s in sessions]
    for f in (indicators.fixed_context, indicators.dead_weight, indicators.interventions,
              indicators.cost, indicators.hooks, indicators.commits):
        f(sessions)
    assert before == [(s.id, len(s.responses), s.tokens.total) for s in sessions]


def test_cross_check_command_prints_counts_without_names(capsys):
    assert indicators.main(["--config", str(CONFIG)]) == 0
    output = capsys.readouterr().out
    assert "peso_morto.skills" in output
    assert "nunca-usada" not in output            # names only with --nomes
    assert indicators.main(["--config", str(CONFIG), "--nomes"]) == 0
    assert "nunca-usada" in capsys.readouterr().out


# --- goal 008 ------------------------------------------------------------------

def test_skill_by_command_counts_only_if_in_the_session_list(sessions):
    dw = indicators.dead_weight(sessions).skills
    assert "clear" not in dw.used               # built-in command: not in the list
    assert "nunca-usada" in dw.never_used       # text in a result is not a command
    assert dw.used_outside_list == set()


def test_skill_by_command_does_not_count_in_session_that_does_not_announce_it(sessions):
    # The same skill typed as a command in a session without a list is not a use.
    s6 = next(s for s in sessions if s.id == S6)
    clone = reader.Session(id="x", path=s6.path, project_dir="p",
                          commands=["por-comando"])
    assert indicators.dead_weight([clone]).skills.used == set()


def test_interventions_count_prompts_by_permission_mode(sessions):
    it = indicators.interventions(sessions)
    assert it.by_mode == {"default": 6, "bypassPermissions": 1}
    assert it.by_session[S6].by_mode == {"bypassPermissions": 1, "default": 1}


def test_missing_mode_appears_as_unknown():
    s = reader.Session(id="x", path=Path("x"), project_dir="p")
    s.prompts = [reader.Prompt("P", None, 0, None)]
    assert indicators.interventions([s]).by_mode == {"?": 1}


def test_cross_check_command_without_sessions_exits_cleanly(tmp_path, capsys):
    (tmp_path / "projects").mkdir()
    assert indicators.main(["--config", str(tmp_path)]) == 0
    output = capsys.readouterr()
    assert "nenhuma sessão encontrada" in (output.out + output.err)
