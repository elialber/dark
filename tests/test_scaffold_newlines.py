"""A file the engine created, checked out again with CRLF (goal 053).

Git on Windows usually runs with ``core.autocrlf=true``: a file written by
the engine with LF comes back with CRLF after a commit and a checkout. Only
the line endings changed, so the engine must not see a different file. The
tests write the CRLF bytes themselves, so they run on every system.
"""

from __future__ import annotations

from pathlib import Path

from dark.scaffold import CreateFile, Plan, apply, revert

CONTENT = "# Título\n\nlinha um\nlinha dois\n"
PATH = "notas/nota.md"


def plan(*ops, module="mod-a") -> Plan:
    return Plan(module=module, version="1.0.0", operations=tuple(ops))


def crlf(text: str) -> bytes:
    return text.replace("\n", "\r\n").encode("utf-8")


def test_existing_file_differing_only_in_line_endings_is_already_present(tmp_path):
    (tmp_path / "notas").mkdir()
    (tmp_path / PATH).write_bytes(crlf(CONTENT))
    out = apply(tmp_path, plan(CreateFile(PATH, CONTENT)))
    assert [s.status for s in out.steps] == ["already_present"], out.steps
    assert (tmp_path / PATH).read_bytes() == crlf(CONTENT)


def test_reapply_after_checkout_with_crlf_is_already_applied(tmp_path):
    p = plan(CreateFile(PATH, CONTENT))
    assert [s.status for s in apply(tmp_path, p).steps] == ["new"]
    (tmp_path / PATH).write_bytes(crlf(CONTENT))  # what autocrlf leaves
    out = apply(tmp_path, p)
    assert [s.status for s in out.steps] == ["already_applied"], out.steps


def test_revert_after_checkout_with_crlf_removes_the_file(tmp_path):
    assert [s.status for s in apply(tmp_path, plan(CreateFile(PATH, CONTENT))).steps] == ["new"]
    (tmp_path / PATH).write_bytes(crlf(CONTENT))
    out = revert(tmp_path, "mod-a")
    assert [s.status for s in out.steps] == ["reverted"], out.steps
    assert not (tmp_path / PATH).exists()


def test_other_differences_are_still_a_conflict(tmp_path):
    (tmp_path / "notas").mkdir()
    (tmp_path / PATH).write_bytes(crlf(CONTENT.replace("dois", "três")))
    out = apply(tmp_path, plan(CreateFile(PATH, CONTENT)))
    assert [s.status for s in out.steps] == ["conflict"]
    assert "conteúdo diferente" in out.steps[0].reason


def test_revert_keeps_a_file_edited_beyond_line_endings(tmp_path):
    apply(tmp_path, plan(CreateFile(PATH, CONTENT)))
    (tmp_path / PATH).write_bytes(crlf(CONTENT + "minha linha\n"))
    out = revert(tmp_path, "mod-a")
    assert "kept" in [s.status for s in out.steps]
    assert (tmp_path / PATH).exists()


def test_lone_carriage_returns_are_not_line_endings(tmp_path):
    # Only CRLF pairs are folded; a bare CR is content.
    (tmp_path / "notas").mkdir()
    (tmp_path / PATH).write_bytes(CONTENT.replace("\n", "\r").encode("utf-8"))
    out = apply(tmp_path, plan(CreateFile(PATH, CONTENT)))
    assert [s.status for s in out.steps] == ["conflict"]


def _checkout_with_crlf(repo: Path, paths: list[str]) -> None:
    for rel in paths:
        f = repo / rel
        f.write_bytes(f.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))


def test_graphify_verify_accepts_its_files_with_crlf(tmp_path):
    from dark.scaffold import graphify, install
    install(graphify.Graphify(), tmp_path)
    files = [path for path, _, _ in graphify._files()]
    _checkout_with_crlf(tmp_path, files)
    detail = graphify.Graphify().verify(tmp_path).detail
    assert "alterado depois da aplicação" not in detail, detail
    # A real edit is still reported.
    (tmp_path / files[0]).write_bytes(b"mine\r\n")
    assert f"alterado depois da aplicação: {files[0]}" in graphify.Graphify().verify(
        tmp_path).detail


def test_langfuse_verify_accepts_its_files_with_crlf(tmp_path):
    from dark.scaffold import install, langfuse
    install(langfuse.Langfuse(), tmp_path)
    _checkout_with_crlf(tmp_path, [langfuse.COMPOSE_PATH, langfuse.ENV_EXAMPLE_PATH])
    detail = langfuse.Langfuse().verify(tmp_path).detail
    assert "diferente do aplicado" not in detail, detail
    (tmp_path / langfuse.COMPOSE_PATH).write_bytes(b"services: {}\r\n")
    assert f"diferente do aplicado: {langfuse.COMPOSE_PATH}" in langfuse.Langfuse().verify(
        tmp_path).detail
