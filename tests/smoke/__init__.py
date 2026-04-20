"""smoke — boot-surface regression tests.

Per CLAUDE.md R14, every change to ``vessal start`` / ``vessal init`` /
``vessal create`` / ``vessal`` wizard TUI must ship with at least one test
here that exercises the first-run flow end-to-end.

These tests spawn a real ``python -m vessal.cli`` subprocess so that we
validate the same bytes the user would see on stderr — no in-process mocking.
"""
