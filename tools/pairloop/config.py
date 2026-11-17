"""Loop limits and settings, read from ``pair/loop.toml``."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PATH = Path("pair/loop.toml")


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class SessionLimits:
    max_turns: int
    timeout_minutes: float


@dataclass(frozen=True)
class Config:
    cycles: int = 3
    max_parallel_executors: int = 4
    round_token_budget: int = 150_000_000
    round_wall_clock_minutes: float = 600.0
    reviewer: SessionLimits = SessionLimits(200, 60)
    executor: SessionLimits = SessionLimits(300, 120)
    model: str = ""
    base_branch: str = "main"
    remote: str = "origin"
    push: bool = True
    test_command: tuple[str, ...] = ("python", "-m", "pytest", "-q")
    claude_command: tuple[str, ...] = ("claude",)
    config_dir: str = ""
    permission_mode: str = "bypassPermissions"
    persist_sessions: bool = True
    setting_sources: str = ""
    state_dir: str = "local/pairloop"
    reports_dir: str = "pair/rodadas"
    extra_env: dict[str, str] = field(default_factory=dict)


def _limits(raw: dict, name: str, default: SessionLimits) -> SessionLimits:
    sec = raw.get(name, {})
    return SessionLimits(
        int(sec.get("max_turns", default.max_turns)),
        float(sec.get("timeout_minutes", default.timeout_minutes)),
    )


def from_dict(raw: dict) -> Config:
    d = Config()
    rnd = raw.get("round", {})
    ses = raw.get("session", {})
    git = raw.get("git", {})
    chk = raw.get("checks", {})
    cla = raw.get("claude", {})
    pth = raw.get("paths", {})
    cfg = Config(
        cycles=int(rnd.get("cycles", d.cycles)),
        max_parallel_executors=int(
            rnd.get("max_parallel_executors", d.max_parallel_executors)),
        round_token_budget=int(rnd.get("token_budget", d.round_token_budget)),
        round_wall_clock_minutes=float(
            rnd.get("wall_clock_minutes", d.round_wall_clock_minutes)),
        reviewer=_limits(ses, "reviewer", d.reviewer),
        executor=_limits(ses, "executor", d.executor),
        model=str(ses.get("model", d.model)),
        base_branch=str(git.get("base_branch", d.base_branch)),
        remote=str(git.get("remote", d.remote)),
        push=bool(git.get("push", d.push)),
        test_command=tuple(chk.get("test_command", d.test_command)),
        claude_command=tuple(cla.get("command", d.claude_command)),
        config_dir=str(cla.get("config_dir", d.config_dir)),
        permission_mode=str(cla.get("permission_mode", d.permission_mode)),
        persist_sessions=bool(cla.get("persist_sessions", d.persist_sessions)),
        setting_sources=str(cla.get("setting_sources", d.setting_sources)),
        state_dir=str(pth.get("state_dir", d.state_dir)),
        reports_dir=str(pth.get("reports_dir", d.reports_dir)),
        extra_env={str(k): str(v) for k, v in cla.get("env", {}).items()},
    )
    if cfg.cycles < 1:
        raise ConfigError("round.cycles deve ser pelo menos 1")
    if cfg.max_parallel_executors < 1:
        raise ConfigError("round.max_parallel_executors deve ser pelo menos 1")
    if not cfg.test_command:
        raise ConfigError("checks.test_command não pode ser vazio")
    return cfg


def load(path: Path) -> Config:
    try:
        with open(path, "rb") as fh:
            raw = tomllib.load(fh)
    except FileNotFoundError as exc:
        raise ConfigError(f"arquivo de limites não encontrado: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: TOML inválido: {exc}") from exc
    return from_dict(raw)
