"""Prompts the orchestrator sends to each session.

The reviewer's role lives in ``.claude/agents/pair-reviewer.md``; these
prompts only carry the parameters of one session.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass


@dataclass
class ReviewParams:
    round_no: int
    cycle: int
    cycles: int
    closing: bool
    base_branch: str
    remote: str
    push: bool
    test_command: tuple[str, ...]
    output_path: str
    diary_path: str
    report_path: str
    to_review: list[dict]
    pending_decisions: list[dict]
    stop_reason: str
    spend: str
    max_batches: int


def reviewer_prompt(p: ReviewParams) -> str:
    if p.to_review:
        branches = "\n".join(
            f"- branch `{b['branch']}` (goal {b['goal']}, batch "
            f"`{b['file']}`, diary `pair/diario/{b['goal']}.md`)"
            for b in p.to_review)
    else:
        branches = ("- none from this round; review any branch the "
                    "roadmap lists as in progress and waiting for review")
    pending = ("\n".join(f"- {d.get('id', '?')}: {d.get('question', '')}"
                         for d in p.pending_decisions)
               or "- none")
    push = (f"the orchestrator pushes `{p.base_branch}` to `{p.remote}` "
            "after its own tests and checks, and deletes the merged branches "
            "from the remote; never push anything yourself"
            if p.push else
            "off for this round; never push anything yourself")
    lines = [
        f"Pair loop, round {p.round_no:03d}, cycle {p.cycle} of {p.cycles}.",
        "",
        f"Base branch: `{p.base_branch}` (checked out in this directory). "
        f"Merge accepted branches into it and nowhere else.",
        f"Remote: `{p.remote}`. Push: {push}.",
        f"Test command: `{shlex.join(p.test_command)}`.",
        "Scratch directory for clean copies and throwaway scripts: "
        "$PAIRLOOP_SCRATCH. Nested Claude Code sessions, if any, must set "
        "CLAUDE_CONFIG_DIR to a directory under it.",
        "",
        "Branches to review:",
        branches,
        "",
        "Decisions already waiting for the user:",
        pending,
        "",
        f"Spend so far in this round: {p.spend}.",
        "",
        f"Review diary: `{p.diary_path}`.",
        f"Cycle output (JSON): `{p.output_path}`.",
    ]
    if p.closing:
        lines += [
            "",
            "The round is closing. Do not write new batches (leave "
            "`batches` empty). Review and merge what is ready, then write "
            f"the round report at `{p.report_path}`.",
            f"Why the round stops: {p.stop_reason}.",
        ]
    else:
        lines += [
            "",
            f"Write at most {p.max_batches} batches for this cycle "
            "(one main and the rest parallel, with exclusive files). If you "
            "set `stop`, also write the round report at "
            f"`{p.report_path}`.",
        ]
    lines += ["", "Follow your definition. Finish by committing on the base "
              "branch; do not push."]
    return "\n".join(lines)


@dataclass
class ExecutorParams:
    batch_file: str
    goal: str
    branch: str
    worktree: str
    base_branch: str
    remote: str
    push: bool
    resumed: bool


def executor_prompt(p: ExecutorParams) -> str:
    push = (f"push it with `git push -u {p.remote} {p.branch}`" if p.push
            else "do not push (push is off for this round)")
    lines = [
        "You are the executor in this repository's pair loop.",
        "",
        f"Execute the batch in `{p.batch_file}` (goal {p.goal}). You are in "
        f"the worktree `{p.worktree}`, on branch `{p.branch}`.",
        "Read `CLAUDE.md` and the batch first. Where the batch is silent, "
        "CLAUDE.md applies.",
        "",
        "Rules of the loop, enforced by hooks:",
        f"- work only in this worktree and in $PAIRLOOP_SCRATCH;",
        f"- never touch `{p.base_branch}` or `main`, never merge, never "
        "force-push;",
        "- never edit `tools/pairloop/`, `.claude/agents/pair-reviewer.md`, "
        "`pair/loop.toml`, `pair/DIRECAO.md`, `docs/visao.md` or "
        "`docs/origem/`;",
        "- Claude Code test sessions, if the batch asks for any, set "
        "CLAUDE_CONFIG_DIR to a directory under $PAIRLOOP_SCRATCH.",
        "",
        "Never ask the user anything: when a decision is missing, adopt a "
        "default, record it in the diary as \"padrão a confirmar\" and go on.",
        "",
        f"When done: write `pair/diario/{p.goal}.md` in Portuguese, commit "
        f"(without -q) on `{p.branch}`, {push}, and stop. Do not update "
        "`pair/ESTADO.md`; the reviewer does it when merging.",
    ]
    if p.resumed:
        lines += ["", "An earlier session on this batch was interrupted. "
                  "Look at the worktree, the branch log and any diary draft, "
                  "and continue from there."]
    return "\n".join(lines)
