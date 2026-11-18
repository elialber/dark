"""Goal 036: `dark iniciar` and `dark remover` on throwaway repositories."""

import hashlib
import os
import subprocess
from pathlib import Path

import pytest

from dark import cli
from dark.scaffold import base

USER_CLAUDE = b"# Mine\n\nUser rules.\r\n"
USER_GITIGNORE = b"*.log\r\n\r\n#  odd   spacing\n/build"      # CRLF, no final newline


def snapshot(root: Path) -> dict:
    """Every file (hash) and directory under root, empty ones included."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for d in dirnames:
            out[os.path.relpath(os.path.join(dirpath, d), root)] = "<dir>"
        for f in filenames:
            p = os.path.join(dirpath, f)
            out[os.path.relpath(p, root)] = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    return out


def git_init(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    return path


@pytest.fixture
def empty(tmp_path):
    return git_init(tmp_path / "empty")


@pytest.fixture
def with_user_files(tmp_path):
    repo = git_init(tmp_path / "user")
    (repo / "CLAUDE.md").write_bytes(USER_CLAUDE)
    (repo / ".gitignore").write_bytes(USER_GITIGNORE)
    return repo


@pytest.fixture
def with_cases(tmp_path):
    repo = git_init(tmp_path / "cases")
    (repo / "evals" / "cases").mkdir(parents=True)
    (repo / "evals" / "cases" / "x.toml").write_bytes(b'id = "x"\n')
    return repo


def run(capsys, *argv):
    capsys.readouterr()
    code = cli.main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_empty_repo_apply_twice_then_remove_is_byte_identical(empty, capsys):
    before = snapshot(empty)
    code, out, _ = run(capsys, "iniciar", str(empty), "--aplicar")
    assert code == 0
    assert (empty / "CLAUDE.md").is_file()
    assert (empty / "evals" / "cases" / "LEIAME.md").is_file()
    assert (empty / "evals" / "cases" / "modelo.toml.modelo").is_file()
    applied = snapshot(empty)
    code, out, _ = run(capsys, "iniciar", str(empty), "--aplicar")
    assert code == 0
    assert "já aplicado" in out
    assert snapshot(empty) == applied
    code, out, _ = run(capsys, "remover", "base", str(empty))
    assert code == 0
    assert snapshot(empty) == before


def test_plan_without_apply_writes_nothing(empty, capsys):
    before = snapshot(empty)
    code, out, _ = run(capsys, "iniciar", str(empty))
    assert code == 0
    assert "CLAUDE.md" in out and "--aplicar" in out
    assert snapshot(empty) == before


def test_user_claude_md_and_gitignore_are_untouched(with_user_files, capsys):
    before = snapshot(with_user_files)
    code, out, _ = run(capsys, "iniciar", str(with_user_files))
    assert code == 0
    assert "já existe" in out
    assert snapshot(with_user_files) == before
    run(capsys, "iniciar", str(with_user_files), "--aplicar")
    assert (with_user_files / "CLAUDE.md").read_bytes() == USER_CLAUDE
    assert (with_user_files / ".gitignore").read_bytes() == USER_GITIGNORE
    assert (with_user_files / "evals" / "cases" / "LEIAME.md").is_file()
    code, _, _ = run(capsys, "remover", "base", str(with_user_files))
    assert code == 0
    assert snapshot(with_user_files) == before


def test_user_cases_dir_is_untouched(with_cases, capsys):
    before = snapshot(with_cases)
    run(capsys, "iniciar", str(with_cases), "--aplicar")
    assert (with_cases / "CLAUDE.md").is_file()
    assert not (with_cases / "evals" / "cases" / "LEIAME.md").exists()
    assert (with_cases / "evals" / "cases" / "x.toml").read_bytes() == b'id = "x"\n'
    code, _, _ = run(capsys, "remover", "base", str(with_cases))
    assert code == 0
    assert snapshot(with_cases) == before


def test_edited_claude_md_stays_with_warning(empty, capsys):
    run(capsys, "iniciar", str(empty), "--aplicar")
    edited = (empty / "CLAUDE.md")
    edited.write_text(edited.read_text(encoding="utf-8") + "\n- my rule\n", encoding="utf-8")
    content = edited.read_bytes()
    code, out, _ = run(capsys, "remover", "base", str(empty))
    assert code == 1
    assert edited.read_bytes() == content
    assert "mantido" in out
    assert not (empty / "evals").exists()


def test_remove_never_installed_module(empty, capsys):
    before = snapshot(empty)
    code, out, err = run(capsys, "remover", "base", str(empty))
    assert code == 0
    assert "nunca foi aplicado" in out
    assert snapshot(empty) == before


def test_unknown_module_is_bad_input(empty, capsys):
    code, out, err = run(capsys, "remover", "nada", str(empty))
    assert code == 2
    assert "desconhecido" in err


def test_bad_paths_give_a_message_and_code_2(tmp_path, capsys):
    plain = tmp_path / "plain"
    plain.mkdir()
    a_file = tmp_path / "file.txt"
    a_file.write_text("x")
    for target in (plain, a_file, tmp_path / "missing"):
        for argv in (("iniciar", str(target)), ("remover", "base", str(target))):
            code, out, err = run(capsys, *argv)
            assert code == 2, argv
            assert "Traceback" not in err
            assert any(w in err for w in ("repositório git", "diretório", "não existe"))


def test_claude_md_as_directory_is_existing_not_an_error(empty, capsys):
    (empty / "CLAUDE.md").mkdir()
    before = snapshot(empty)
    code, out, err = run(capsys, "iniciar", str(empty), "--aplicar")
    assert code == 0 and "Traceback" not in err
    assert (empty / "CLAUDE.md").is_dir()
    assert snapshot(empty) != before          # evals/cases created
    run(capsys, "remover", "base", str(empty))
    assert snapshot(empty) == before


def test_corrupt_manifest_is_reported(empty, capsys):
    (empty / ".dark-scaffold.json").write_text("{not json", encoding="utf-8")
    for argv in (("remover", "base", str(empty)), ("iniciar", str(empty), "--aplicar"),
                 ("iniciar", str(empty))):
        code, out, err = run(capsys, *argv)
        assert code == 2, argv
        assert "Traceback" not in err and ".dark-scaffold.json" in err


def test_conflict_applies_nothing_and_exits_1(empty, capsys):
    (empty / "evals").write_text("a file where a directory is needed", encoding="utf-8")
    before = snapshot(empty)
    code, out, err = run(capsys, "iniciar", str(empty), "--aplicar")
    assert code == 1
    assert "conflito" in out and "Traceback" not in err
    assert snapshot(empty) == before
    assert not (empty / "CLAUDE.md").exists()


def test_state_line_counts_project_harness_only(empty, capsys):
    (empty / ".claude" / "skills" / "s").mkdir(parents=True)
    (empty / ".claude" / "skills" / "s" / "SKILL.md").write_text(
        "---\nname: s\ndescription: d\n---\nbody\n", encoding="utf-8")
    code, out, _ = run(capsys, "iniciar", str(empty))
    assert code == 0
    assert "peça(s) de harness" in out


def test_module_creates_no_rules_skills_or_hooks(empty):
    plan = base.Base().plan(empty)
    paths = {op.path for op in plan.operations}
    assert paths == {"CLAUDE.md", "evals/cases/LEIAME.md", "evals/cases/modelo.toml.modelo"}
    text = "\n".join(op.content for op in plan.operations)
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings.count("## Regras derivadas de falhas observadas") == 1
    claude = next(op.content for op in plan.operations if op.path == "CLAUDE.md")
    assert not [line for line in claude.splitlines() if line.startswith(("- ", "* "))]


def test_help_is_in_portuguese(capsys):
    for argv in (["iniciar", "--help"], ["remover", "--help"]):
        with pytest.raises(SystemExit):
            cli.main(argv)
        assert "--aplicar" in capsys.readouterr().out or argv[0] == "remover"


def test_subfolder_of_a_repository_is_refused_not_walked_up(empty, capsys):
    sub = empty / "sub"
    sub.mkdir()
    before = snapshot(empty)
    code, out, err = run(capsys, "iniciar", str(sub), "--aplicar")
    assert code == 2
    assert str(empty) in err
    assert snapshot(empty) == before
