"""普段の運用が、既存の 3 コマンドをどの順で呼ぶかを検証する。"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from starcore.routine import routine_args, run_routine, run_step


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


def test_run_step_returns_child_status(tmp_path: Path):
    code = run_step(
        [sys.executable, "-c", "import sys; sys.stderr.write('err'); raise SystemExit(0)"],
        tmp_path,
    )
    assert code == 0


def _pythonw_path() -> str | None:
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        candidate = exe[: -len("python.exe")] + "pythonw.exe"
        if os.path.isfile(candidate):
            return candidate
    return None


@pytest.mark.skipif(_pythonw_path() is None, reason="pythonw.exe が無い")
def test_pythonw_child_can_write_stderr(tmp_path: Path):
    """start_gui.pyw と同じく pythonw から子を起動しても stderr が使える。"""
    parent = tmp_path / "parent.py"
    parent.write_text(
        "\n".join([
            "import sys",
            "from pathlib import Path",
            "from starcore.routine import run_step",
            "code = run_step(",
            "    [sys.executable, '-c', 'import sys; sys.stderr.write(\"ERR\\\\n\"); print(\"OUT\")'],",
            "    Path.cwd(),",
            ")",
            "raise SystemExit(code)",
            "",
        ]),
        encoding="utf-8",
    )
    pythonw = _pythonw_path()
    assert pythonw is not None
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    completed = subprocess.run(
        [pythonw, "-u", str(parent)],
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    assert completed.returncode == 0
    assert "OUT" in completed.stdout
    assert "ERR" in completed.stdout
