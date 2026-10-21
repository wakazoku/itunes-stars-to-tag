"""普段の運用 (評価の書き込み → ファイル差分 → ミラーコピー) を順に実行する。

各段階は既存 CLI をそのまま子プロセスで呼ぶ。評価ロジックはここへ複製しない。
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence


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


def run_routine(apply: bool, python: str, cwd: Path, runner: Runner) -> int:
    """段階を上から実行し、最初に失敗した終了コードを返す。成功時は 0。

    途中で失敗したら、それ以降の段階は実行しない。
    """
    for args in routine_args(apply):
        code = runner([python, "-u", *args], cwd)
        if code != 0:
            return code
    return 0
