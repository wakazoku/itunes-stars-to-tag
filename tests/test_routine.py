"""普段の運用が、既存の 3 コマンドをどの順で呼ぶかを検証する。"""
from __future__ import annotations

from pathlib import Path

from starcore.routine import routine_args, run_routine


def test_dry_run_steps_do_not_write():
    assert routine_args(False) == [
        ["sync_ratings.py", "--dry-run"],
        ["sync_files.py"],
        ["mirror_changed.py", "--dry-run", "--create-missing", "--allow-missing-list"],
    ]


def test_apply_steps_match_scenario_a():
    assert routine_args(True) == [
        ["sync_ratings.py"],
        ["sync_files.py", "--apply"],
        ["mirror_changed.py", "--create-missing"],
    ]


def test_run_stops_after_first_failure(tmp_path: Path):
    calls: list[list[str]] = []

    def runner(argv: list[str], cwd: Path) -> int:
        calls.append(list(argv))
        assert cwd == tmp_path
        return 1

    code = run_routine(True, "py", tmp_path, runner)
    assert code == 1
    assert calls == [["py", "-u", "sync_ratings.py"]]


def test_run_continues_until_the_end_on_success(tmp_path: Path):
    calls: list[str] = []

    def runner(argv: list[str], cwd: Path) -> int:
        calls.append(argv[2])
        return 0

    assert run_routine(False, "py", tmp_path, runner) == 0
    assert calls == ["sync_ratings.py", "sync_files.py", "mirror_changed.py"]
