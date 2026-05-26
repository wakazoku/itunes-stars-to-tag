"""``changed_files.txt`` の読み書き・マージを担う純粋ロジック。

sync_ratings.py / repair_mirror.py の両方で
「既存リスト + 新規分を、重複除去しつつ追記する」処理が必要なため
ここに集約する。Windows パスの大小無視のために
``os.path.normcase`` で比較する点に注意。
"""

from __future__ import annotations

import os
from pathlib import Path


def read_paths(path: Path) -> list[str]:
    """``changed_files.txt`` を読んで、空行を除いたパスリストを返す。

    ファイルが存在しなければ空リスト。
    """
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def merge_paths(existing: list[str], new: list[str]) -> list[str]:
    """``existing`` の後ろに ``new`` を、重複除去しつつ追記したリストを返す。

    - 重複判定は ``os.path.normcase`` (Windows の大文字小文字非依存) で行う
    - 並び順は「既存を先に、その後に新規が出現順で並ぶ」を保つ
    - 両者内の重複も除去される (最初に出現したパス文字列を採用)
    """
    seen: set[str] = set()
    merged: list[str] = []
    for p in list(existing) + list(new):
        key = os.path.normcase(p)
        if key in seen:
            continue
        seen.add(key)
        merged.append(p)
    return merged


def write_paths(path: Path, paths: list[str]) -> None:
    """パスリストを ``changed_files.txt`` 形式 (1行1パス, UTF-8) で書き出す。

    空リストの場合は空ファイルを書く (=既存内容のクリア)。
    """
    content = "\n".join(paths)
    if paths:
        content += "\n"
    path.write_text(content, encoding="utf-8")
