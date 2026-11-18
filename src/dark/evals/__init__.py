"""Evals: case format, validation, mining of candidates and the runner.

Validation runs the acceptance command of the evaluated repository, in a
temporary copy. The runner (`runner`, `rounds`) runs the agent in
non-interactive mode on each case, in a clean copy, with and without the
harness, and records each run. Commands: `python -m dark.evals`.
"""
