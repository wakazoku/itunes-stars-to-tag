"""普段の運用 (評価の書き込み → ファイル差分 → ミラーコピー) を順に実行する。

各段階は既存 CLI をそのまま子プロセスで呼ぶ。評価ロジックはここへ複製しない。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable, IO, Sequence


Runner = Callable[[Sequence[str], Path], int]


def routine_args(apply: bool) -> list[list[str]]:
    """実行するスクリプトと引数。Python 実行ファイルは含まない。

    ``apply`` が偽のときは各段階を dry-run にする。
    コピーは新規ファイルも作る (``--create-missing``)。
    """
    if apply:
        return [
            ["sync_ratings.py"],
            ["sync_files.py", "--apply"],
            ["mirror_changed.py", "--create-missing"],
        ]
    return [
        ["sync_ratings.py", "--dry-run"],
        ["sync_files.py"],
        ["mirror_changed.py", "--dry-run", "--create-missing", "--allow-missing-list"],
    ]


def _child_stream(stream: IO[str] | None):
    """子プロセスに渡す標準入出力。

    GUI は pythonw から起動する。pythonw はコンソールが無いと
    ``sys.stdout`` / ``sys.stderr`` を None にする。そのまま子を起動すると
    tqdm が stderr へ書けず即終了する。親がパイプを持っていればそれを継ぐ。
    """
    if stream is None:
        return subprocess.DEVNULL
    try:
        stream.fileno()
    except (AttributeError, OSError, ValueError):
        return subprocess.DEVNULL
    return stream


def run_step(argv: Sequence[str], cwd: Path) -> int:
    """1 段階を実行し、終了コードを返す。

    標準出力と標準エラーは親と同じ先へ流す。コンソール窓は出さない。
    """
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    completed = subprocess.run(
        list(argv),
        cwd=cwd,
        stdout=_child_stream(sys.stdout),
        stderr=_child_stream(sys.stderr),
        stdin=subprocess.DEVNULL,
        **kwargs,
    )
    return completed.returncode


def run_routine(apply: bool, python: str, cwd: Path, runner: Runner) -> int:
    """段階を上から実行し、最初に失敗した終了コードを返す。成功時は 0。

    途中で失敗したら、それ以降の段階は実行しない。
    """
    for args in routine_args(apply):
        code = runner([python, "-u", *args], cwd)
        if code != 0:
            return code
    return 0
