"""Limit hook for pair loop sessions.

Claude Code runs this file as a PreToolUse hook in every session the
orchestrator starts (it is passed with ``--settings``). It reads the hook
input from stdin and the session context from environment variables set by
the orchestrator, and blocks the tool call (exit code 2, reason on stderr)
when it breaks one of the limits below. Standard library only, and no
imports from the rest of the package, so it runs as a plain script.

Limits enforced here:

- no agent pushes with force, pushes to another remote, rewrites remotes
  or deletes ``main`` (or the round's base branch);
- the reviewer never pushes: the orchestrator pushes the base branch after
  its own checks;
- the executor never pushes to, merges into or checks out the base branch,
  and never merges at all;
- no agent writes git configuration, except its identity (``user.name``,
  ``user.email``) in the repository: configuration can run code later, in
  the orchestrator's own git commands (``core.hooksPath``,
  ``core.fsmonitor``, ``core.sshCommand``, ``alias.*``...);
- no agent writes outside its roots (repository, its worktree) and its
  scratch directories;
- no agent edits the loop itself (``tools/pairloop/``, the reviewer
  definition, ``pair/loop.toml``, ``pair/DIRECAO.md``) or the user's voice
  and origin records (``docs/visao.md``, ``docs/origem/``);
- the reviewer only writes in ``pair/``, ``docs/decisoes.md`` and
  ``docs/roteiro.md``.

Shell commands cannot be fully analysed, and a program the agent writes
(``python -c``, a script) is not seen at all. The checks here catch the
usual forms (redirections, file utilities, ``sed -i``, git). After every
session the orchestrator checks the git history and the content of the
protected files in the working tree; writes outside the repository by such
a program are not caught by any layer (accepted risk, docs/decisoes.md).

Environment:

- ``PAIRLOOP_ROLE``: ``reviewer`` or ``executor``;
- ``PAIRLOOP_ROOTS``: directories where the path rules apply, separated by
  ``os.pathsep``;
- ``PAIRLOOP_SCRATCH``: extra writable directories without path rules;
- ``PAIRLOOP_BASE_BRANCH`` (default ``main``) and ``PAIRLOOP_REMOTE``
  (default ``origin``);
- ``PAIRLOOP_GUARD_LOG``: optional file where each block is appended as a
  JSON line.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REVIEWER = "reviewer"
EXECUTOR = "executor"
ROLES = (REVIEWER, EXECUTOR)

# Paths relative to a repository root. A trailing slash marks a directory.
LOOP_FILES = (
    "tools/pairloop/",
    ".claude/agents/pair-reviewer.md",
    "pair/loop.toml",
    "pair/DIRECAO.md",
)
USER_FILES = (
    "docs/visao.md",
    "docs/origem/",
)
REVIEWER_WRITABLE = (
    "pair/",
    "docs/decisoes.md",
    "docs/roteiro.md",
)

FILE_TOOLS = {
    "Write": "file_path",
    "Edit": "file_path",
    "MultiEdit": "file_path",
    "NotebookEdit": "notebook_path",
}

# git config keys a loop agent may write, in the repository's own file.
CONFIG_WRITABLE = {"user.name", "user.email"}
_CONFIG_READ_FLAGS = {
    "--get", "--get-all", "--get-regexp", "--get-urlmatch", "--get-color",
    "--get-colorbool", "-l", "--list",
}
_CONFIG_WRITE_FLAGS = {
    "--add", "--replace-all", "--unset", "--unset-all",
}
_CONFIG_SECTION_FLAGS = {"--rename-section", "--remove-section", "-e", "--edit"}
_CONFIG_VALUE_OPTS = {
    "-f", "--file", "--blob", "-t", "--type", "--default", "--comment",
    "--value", "--url",
}
_CONFIG_READ_SUBCOMMANDS = {"get", "list"}
_CONFIG_SUBCOMMANDS = {"get", "list", "set", "unset", "rename-section",
                       "remove-section", "edit"}

GIT_MUTATING = {
    "add", "am", "apply", "checkout", "cherry-pick", "clean", "commit",
    "merge", "mv", "pull", "rebase", "reset", "restore", "revert", "rm",
    "stash", "switch", "tag",
}


@dataclass(frozen=True)
class Context:
    role: str
    roots: tuple[Path, ...]
    scratch: tuple[Path, ...] = ()
    base_branch: str = "main"
    remote: str = "origin"
    cwd: Path = field(default_factory=Path.cwd)

    @property
    def protected_branches(self) -> set[str]:
        return {"main", self.base_branch}


def matches(rel: str, patterns: tuple[str, ...]) -> bool:
    for p in patterns:
        if p.endswith("/"):
            if rel == p[:-1] or rel.startswith(p):
                return True
        elif rel == p:
            return True
    return False


def _real(path: Path) -> Path:
    return Path(os.path.realpath(path))


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def resolve(raw: str, cwd: Path) -> Path:
    p = Path(os.path.expanduser(raw))
    if not p.is_absolute():
        p = cwd / p
    return _real(p)


_NULL_DEVICES = {"/dev/null"}


def check_path(path: Path, ctx: Context) -> str | None:
    """Return why writing ``path`` is not allowed, or None."""
    path = _real(path)
    if str(path) == os.devnull:
        return None
    roots = sorted((_real(r) for r in ctx.roots), key=lambda r: len(r.parts),
                   reverse=True)
    for root in roots:
        if _inside(path, root):
            rel = path.relative_to(root).as_posix()
            if rel == ".":
                rel = ""
            if matches(rel, LOOP_FILES):
                return (f"{rel}: o laço não altera a si mesmo; só o usuário "
                        "edita este arquivo.")
            if matches(rel, USER_FILES):
                return (f"{rel}: a voz do usuário e os registros de origem "
                        "são intocáveis; só o usuário edita.")
            if ctx.role == REVIEWER and not matches(rel, REVIEWER_WRITABLE):
                return (f"{rel}: o revisor só escreve em pair/, "
                        "docs/decisoes.md e docs/roteiro.md.")
            return None
    for extra in ctx.scratch:
        if _inside(path, _real(extra)):
            return None
    return (f"{path}: fora do repositório, dos worktrees e do diretório de "
            "rascunho da sessão (use $PAIRLOOP_SCRATCH).")


# --- shell parsing -------------------------------------------------------

_HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][\w.-]*)\1")
_SEPARATORS = {";", "&&", "||", "|", "&", "|&", "(", ")", ";;", "{", "}"}
_WRAPPERS = {"sudo", "env", "command", "exec", "nohup", "time", "nice",
             "builtin"}


def _strip_heredocs(command: str) -> str:
    out: list[str] = []
    pending: list[tuple[str, bool]] = []
    for line in command.split("\n"):
        if pending:
            delim, dash = pending[0]
            if (line.lstrip("\t") if dash else line).strip() == delim:
                pending.pop(0)
            continue
        out.append(line)
        for m in _HEREDOC.finditer(line):
            pending.append((m.group(2), m.group(0).startswith("<<-")))
    return "\n".join(out)


@dataclass
class Simple:
    argv: list[str]
    redirects: list[str]


def split_commands(command: str) -> list[Simple]:
    """Split a shell command line into simple commands.

    Raises ValueError when the line cannot be tokenized.
    """
    text = _strip_heredocs(command.replace("\\\n", " "))
    text = text.replace("\n", " ; ")
    lex = shlex.shlex(text, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    tokens = list(lex)
    result: list[Simple] = []
    cur = Simple([], [])
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in _SEPARATORS:
            if cur.argv or cur.redirects:
                result.append(cur)
            cur = Simple([], [])
        elif set(tok) <= set("<>&|") and (">" in tok or "<" in tok):
            target = tokens[i + 1] if i + 1 < len(tokens) else ""
            i += 1
            if cur.argv and cur.argv[-1].isdigit():
                cur.argv.pop()
            if ">" in tok and not (tok.endswith("&") and target.isdigit()) \
                    and target != "-":
                cur.redirects.append(target)
        else:
            cur.argv.append(tok)
        i += 1
    if cur.argv or cur.redirects:
        result.append(cur)
    return result


def _strip_wrappers(argv: list[str]) -> list[str]:
    i = 0
    while i < len(argv):
        a = argv[i]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", a):
            i += 1
        elif a in _WRAPPERS:
            i += 1
            while i < len(argv) and argv[i].startswith("-"):
                i += 1
        else:
            break
    return argv[i:]


def _operands(args: list[str]) -> list[str]:
    out, after_dashes = [], False
    for a in args:
        if after_dashes:
            out.append(a)
        elif a == "--":
            after_dashes = True
        elif not a.startswith("-") or a == "-":
            out.append(a)
    return out


def written_paths(argv: list[str]) -> list[str]:
    """Paths a simple (non-git) command writes, as far as can be told."""
    if not argv:
        return []
    name = os.path.basename(argv[0])
    args = argv[1:]
    ops = _operands(args)
    if name in {"rm", "rmdir", "touch", "mkdir", "unlink", "tee", "shred"}:
        return ops
    if name == "truncate":
        vals = []
        skip = False
        for a in args:
            if skip:
                skip = False
            elif a in ("-s", "--size", "-r", "--reference"):
                skip = True
            elif not a.startswith("-"):
                vals.append(a)
        return vals
    if name in {"chmod", "chown", "chgrp"}:
        return ops[1:]
    if name == "mv":
        return ops
    if name in {"cp", "ln", "install", "rsync"}:
        return ops[-1:] if len(ops) >= 2 else []
    if name == "sed":
        if not any(a == "-i" or a.startswith("-i") or a.startswith("--in-place")
                   or (a.startswith("-") and not a.startswith("--")
                       and "i" in a[1:]) for a in args):
            return []
        explicit_script = any(a in ("-e", "-f") or a.startswith("--expression")
                              for a in args)
        files, skip = [], False
        for a in args:
            if skip:
                skip = False
            elif a in ("-e", "-f"):
                skip = True
            elif a.startswith("-"):
                continue
            else:
                files.append(a)
        return files if explicit_script else files[1:]
    if name == "dd":
        return [a[3:] for a in args if a.startswith("of=")]
    return []


def _current_branch(cwd: Path) -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                           cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _branch_name(ref: str) -> str:
    for prefix in ("refs/heads/", "heads/"):
        if ref.startswith(prefix):
            return ref[len(prefix):]
    return ref


def check_git(argv: list[str], cwd: Path, ctx: Context) -> str | None:
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "-C" and i + 1 < len(argv):
            cwd = resolve(argv[i + 1], cwd)
            i += 2
        elif a == "-c" and i + 1 < len(argv):
            key = argv[i + 1].split("=", 1)[0].lower()
            if key.startswith(("remote.", "url.", "push.", "branch.")):
                return f"git -c {key}: não é permitido mudar remoto ou push."
            i += 2
        elif a.startswith("--git-dir") or a.startswith("--work-tree"):
            return "git --git-dir/--work-tree: não é permitido no laço."
        elif a.startswith("-"):
            i += 1
        else:
            break
    if i >= len(argv):
        return None
    sub, args = argv[i], argv[i + 1:]

    if sub in GIT_MUTATING:
        allowed = ctx.roots + ctx.scratch
        if not any(_inside(_real(cwd), _real(r)) for r in allowed):
            return (f"git {sub} em {cwd}: fora do repositório ou worktree "
                    "desta sessão.")
    if sub in ("rm", "mv") or (sub in ("checkout", "restore")
                               and "--" in args):
        paths = (_operands(args) if sub in ("rm", "mv")
                 else args[args.index("--") + 1:])
        for raw in paths:
            reason = check_path(resolve(raw, cwd), ctx)
            if reason:
                return reason
    if sub == "config":
        return _check_config(args)
    if sub == "push":
        if ctx.role == REVIEWER:
            return ("O revisor não faz push; o orquestrador faz, depois dos "
                    "testes e da conferência do histórico.")
        return _check_push(args, cwd, ctx)
    if sub == "remote" and args and args[0] in {
            "add", "set-url", "rename", "remove", "rm", "set-head"}:
        return "git remote: não é permitido alterar remotos."
    if sub == "branch":
        flags = [a for a in args if a.startswith("-")]
        destructive = any(f in ("-d", "-D", "--delete", "-m", "-M", "--move",
                                "-f", "--force") for f in flags)
        if destructive and ctx.protected_branches & set(_operands(args)):
            return "git branch: não é permitido apagar, mover ou renomear main."
    if sub == "update-ref":
        refs = {_branch_name(a) for a in _operands(args)}
        if ctx.protected_branches & refs and (
                "-d" in args or ctx.role == EXECUTOR):
            return "git update-ref: não é permitido mexer em main."
    if ctx.role == EXECUTOR:
        if sub == "merge":
            return "O executor nunca faz merge; o revisor junta as branches."
        if sub in ("checkout", "switch"):
            if ctx.protected_branches & set(_operands(args)):
                return "O executor não muda para a branch base."
        if sub == "worktree" and args and args[0] in ("remove", "prune",
                                                      "move"):
            return "O executor não remove nem move worktrees."
    return None


def _check_push(args: list[str], cwd: Path, ctx: Context) -> str | None:
    positional: list[str] = []
    delete = False
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--force") or a in ("--mirror", "--all", "--prune"):
            return f"git push {a}: push forçado ou em massa não é permitido."
        if a in ("-o", "--push-option", "--receive-pack", "--exec"):
            i += 2
            continue
        if a.startswith("--repo="):
            positional.insert(0, a.split("=", 1)[1])
        elif a in ("-d", "--delete"):
            delete = True
        elif a.startswith("-") and not a.startswith("--"):
            if "f" in a[1:]:
                return "git push -f: push forçado não é permitido."
            if "d" in a[1:]:
                delete = True
        elif not a.startswith("-"):
            positional.append(a)
        i += 1
    remote = positional[0] if positional else None
    refspecs = positional[1:]
    if remote is not None and remote != ctx.remote:
        return (f"git push {remote}: só é permitido o remoto "
                f"{ctx.remote}.")
    for spec in refspecs:
        if spec.startswith("+"):
            return f"git push {spec}: push forçado não é permitido."
    if delete:
        if ctx.role == EXECUTOR:
            return "O executor não apaga branches remotas."
        names = {_branch_name(s.split(":")[-1]) for s in refspecs}
        if ctx.protected_branches & names:
            return "git push --delete: não é permitido apagar main."
        return None
    if ctx.role == EXECUTOR and not refspecs:
        return ("O executor faz push com a branch explícita: "
                "git push -u origin <sua-branch>.")
    targets: set[str] = set()
    for spec in refspecs:
        src, _, dst = spec.partition(":")
        if _ and not src:
            name = _branch_name(dst)
            if name in ctx.protected_branches:
                return f"git push {spec}: não é permitido apagar {name}."
            if ctx.role == EXECUTOR:
                return "O executor não apaga branches remotas."
            continue
        target = dst or src
        if target == "HEAD":
            target = _current_branch(cwd) or "HEAD"
        targets.add(_branch_name(target))
    if not refspecs:
        current = _current_branch(cwd)
        if current:
            targets.add(current)
    if ctx.role == EXECUTOR and targets & ctx.protected_branches:
        return "O executor nunca faz push para a branch base nem para main."
    return None


def _check_config(args: list[str]) -> str | None:
    """Block git config writes, except the identity in the repository."""
    blocked = ("git config: o laço só lê a configuração do git (e grava "
               "user.name e user.email no repositório); configuração pode "
               "executar código depois, nos comandos do orquestrador.")
    operands: list[str] = []
    mode = None            # "read", "write" or "section"
    outside = False
    i = 0
    while i < len(args):
        a = args[i]
        name = a.split("=", 1)[0]
        if name in ("-f", "--file", "--blob"):
            outside = True     # another file: only the repository's own
        if a in _CONFIG_VALUE_OPTS:
            i += 2
            continue
        if a.startswith("--") and "=" in a and name in _CONFIG_VALUE_OPTS:
            pass
        elif a in ("--global", "--system"):
            outside = True
        elif a in _CONFIG_SECTION_FLAGS:
            mode = "section"
        elif a in _CONFIG_WRITE_FLAGS:
            mode = mode or "write"
        elif a in _CONFIG_READ_FLAGS:
            mode = mode or "read"
        elif not a.startswith("-"):
            operands.append(a)
        i += 1
    if mode is None and operands and operands[0] in _CONFIG_SUBCOMMANDS:
        verb = operands.pop(0)
        mode = ("read" if verb in _CONFIG_READ_SUBCOMMANDS
                else "section" if verb in ("rename-section", "remove-section",
                                           "edit")
                else "write")
    if mode is None:
        mode = "write" if len(operands) >= 2 else "read"
    if mode == "read":
        return None
    if mode == "section" or outside or not operands:
        return blocked
    if operands[0].lower() not in CONFIG_WRITABLE:
        return blocked
    return None


def check_bash(command: str, ctx: Context) -> str | None:
    try:
        commands = split_commands(command)
    except ValueError:
        lowered = command
        for rel in LOOP_FILES + USER_FILES:
            if rel.rstrip("/") in lowered:
                return ("Comando que não consegui analisar e que cita um "
                        f"arquivo protegido ({rel}). Reescreva-o de forma "
                        "mais simples.")
        if re.search(r"\bpush\b", command):
            return ("git push em comando que não consegui analisar. "
                    "Rode o push como comando separado.")
        return None
    cwd = ctx.cwd
    for simple in commands:
        argv = _strip_wrappers(simple.argv)
        for target in simple.redirects:
            if target in _NULL_DEVICES:      # also in Git Bash on Windows
                continue
            reason = check_path(resolve(target, cwd), ctx)
            if reason:
                return reason
        if not argv:
            continue
        name = os.path.basename(argv[0])
        if name == "cd":
            if len(argv) > 1 and argv[1] != "-":
                cwd = resolve(argv[1], cwd)
            continue
        if name in ("bash", "sh", "zsh") and "-c" in argv:
            idx = argv.index("-c")
            if idx + 1 < len(argv):
                inner = Context(ctx.role, ctx.roots, ctx.scratch,
                                ctx.base_branch, ctx.remote, cwd)
                reason = check_bash(argv[idx + 1], inner)
                if reason:
                    return reason
            continue
        if name == "git":
            reason = check_git(argv, cwd, ctx)
            if reason:
                return reason
            continue
        for target in written_paths(argv):
            if target in _NULL_DEVICES:
                continue
            reason = check_path(resolve(target, cwd), ctx)
            if reason:
                return reason
    return None


def check_tool(tool_name: str, tool_input: dict, ctx: Context) -> str | None:
    """Return why the tool call is blocked, or None to let it run."""
    if ctx.role not in ROLES:
        return "Sessão do laço sem papel definido (PAIRLOOP_ROLE)."
    if tool_name in FILE_TOOLS:
        raw = tool_input.get(FILE_TOOLS[tool_name])
        if not isinstance(raw, str) or not raw:
            return None
        return check_path(resolve(raw, ctx.cwd), ctx)
    if tool_name == "Bash":
        command = tool_input.get("command")
        if isinstance(command, str):
            return check_bash(command, ctx)
    return None


def context_from_env(env: dict[str, str], cwd: Path) -> Context:
    def paths(name: str) -> tuple[Path, ...]:
        return tuple(Path(p) for p in env.get(name, "").split(os.pathsep) if p)
    return Context(
        role=env.get("PAIRLOOP_ROLE", ""),
        roots=paths("PAIRLOOP_ROOTS"),
        scratch=paths("PAIRLOOP_SCRATCH"),
        base_branch=env.get("PAIRLOOP_BASE_BRANCH", "main"),
        remote=env.get("PAIRLOOP_REMOTE", "origin"),
        cwd=cwd,
    )


def main() -> int:
    try:
        data = json.load(sys.stdin)
        cwd = Path(data.get("cwd") or os.getcwd())
        ctx = context_from_env(dict(os.environ), cwd)
        reason = check_tool(data.get("tool_name", ""),
                            data.get("tool_input") or {}, ctx)
    except Exception as exc:  # fail closed
        data = {}
        reason = f"Hook de limite falhou ({exc!r}); ação bloqueada."
    if reason is None:
        return 0
    log = os.environ.get("PAIRLOOP_GUARD_LOG")
    if log:
        try:
            with open(log, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "role": os.environ.get("PAIRLOOP_ROLE", ""),
                    "tool": data.get("tool_name", ""),
                    "reason": reason,
                }, ensure_ascii=False) + "\n")
        except OSError:
            pass
    print(f"Bloqueado pelo laço de par: {reason}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
