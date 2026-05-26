"""starcore.changed_list のマージ / I/O ロジックを検証する。"""
from __future__ import annotations

import os
from pathlib import Path

from starcore.changed_list import merge_paths, read_paths, write_paths


# ---------------------------------------------------------------------------
# merge_paths: 並び順保持・重複除去
# ---------------------------------------------------------------------------
def test_merge_paths_appends_new_after_existing():
    existing = [r"C:\a.mp3", r"C:\b.mp3"]
    new = [r"C:\c.mp3", r"C:\d.mp3"]
    assert merge_paths(existing, new) == [
        r"C:\a.mp3",
        r"C:\b.mp3",
        r"C:\c.mp3",
        r"C:\d.mp3",
    ]


def test_merge_paths_removes_duplicate_keeping_existing_first():
    """既存に同じパスがあれば新規ぶんは追加しない。"""
    existing = [r"C:\a.mp3", r"C:\b.mp3"]
    new = [r"C:\b.mp3", r"C:\c.mp3"]
    assert merge_paths(existing, new) == [
        r"C:\a.mp3",
        r"C:\b.mp3",
        r"C:\c.mp3",
    ]


def test_merge_paths_dedups_within_new():
    """new 側に重複があっても 1 度しか入らない。"""
    existing: list[str] = []
    new = [r"C:\a.mp3", r"C:\a.mp3", r"C:\b.mp3"]
    assert merge_paths(existing, new) == [r"C:\a.mp3", r"C:\b.mp3"]


def test_merge_paths_dedups_within_existing():
    """既存ファイルが重複行を持っていた場合も除去される。"""
    existing = [r"C:\a.mp3", r"C:\a.mp3"]
    new = [r"C:\b.mp3"]
    assert merge_paths(existing, new) == [r"C:\a.mp3", r"C:\b.mp3"]


def test_merge_paths_case_insensitive_on_windows():
    """Windows 想定で normcase 比較するため大文字小文字違いは重複扱い。"""
    existing = [r"C:\Music\Song.mp3"]
    new = [r"c:\music\song.mp3"]
    merged = merge_paths(existing, new)
    assert len(merged) == 1
    # 既存側の表記が残る
    assert merged[0] == r"C:\Music\Song.mp3"


def test_merge_paths_empty_inputs():
    assert merge_paths([], []) == []
    assert merge_paths([], [r"C:\a.mp3"]) == [r"C:\a.mp3"]
    assert merge_paths([r"C:\a.mp3"], []) == [r"C:\a.mp3"]


def test_merge_paths_does_not_mutate_inputs():
    existing = [r"C:\a.mp3"]
    new = [r"C:\b.mp3"]
    merge_paths(existing, new)
    assert existing == [r"C:\a.mp3"]
    assert new == [r"C:\b.mp3"]


# ---------------------------------------------------------------------------
# read_paths: 空行スキップ / 末尾改行どちらでも OK / 未存在ファイルは []
# ---------------------------------------------------------------------------
def test_read_paths_missing_file_returns_empty(tmp_path: Path):
    target = tmp_path / "does_not_exist.txt"
    assert read_paths(target) == []


def test_read_paths_skips_blank_lines(tmp_path: Path):
    target = tmp_path / "changed.txt"
    target.write_text(
        "C:\\a.mp3\n\n   \nC:\\b.mp3\n",
        encoding="utf-8",
    )
    assert read_paths(target) == [r"C:\a.mp3", r"C:\b.mp3"]


def test_read_paths_handles_unicode(tmp_path: Path):
    target = tmp_path / "changed.txt"
    p = r"C:\Music\星野源\YELLOW DISC 2020\01 ばらばら.m4a"
    target.write_text(p + "\n", encoding="utf-8")
    assert read_paths(target) == [p]


# ---------------------------------------------------------------------------
# write_paths: 末尾改行・空リスト・round-trip
# ---------------------------------------------------------------------------
def test_write_paths_adds_trailing_newline(tmp_path: Path):
    target = tmp_path / "changed.txt"
    write_paths(target, [r"C:\a.mp3", r"C:\b.mp3"])
    text = target.read_text(encoding="utf-8")
    assert text == "C:\\a.mp3\nC:\\b.mp3\n"


def test_write_paths_empty_list_creates_empty_file(tmp_path: Path):
    target = tmp_path / "changed.txt"
    write_paths(target, [])
    assert target.exists()
    assert target.read_text(encoding="utf-8") == ""


def test_round_trip_preserves_paths(tmp_path: Path):
    target = tmp_path / "changed.txt"
    paths = [
        r"C:\Music\a.mp3",
        r"D:\Music\日本語.m4a",
        r"C:\Music\sub dir\file with space.mp3",
    ]
    write_paths(target, paths)
    assert read_paths(target) == paths


# ---------------------------------------------------------------------------
# 実運用シナリオを模した結合的なケース
# ---------------------------------------------------------------------------
def test_scenario_sync_runs_twice_without_mirror_keeps_first_diff(tmp_path: Path):
    """sync_ratings.py のバグ修正をシナリオで担保する:

    1) sync(1回目) で 3 件を追記
    2) mirror を実行しないまま sync(2回目) を回す。今回の差分は 0 件。
       -> merge_paths(既存3件, []) = 3 件 のまま維持されることを確認する。
    """
    target = tmp_path / "changed_files.txt"

    # 1回目: 既存ファイル無し + 新規 3 件
    first_existing = read_paths(target)
    first_new = [r"C:\a.mp3", r"C:\b.mp3", r"C:\c.mp3"]
    write_paths(target, merge_paths(first_existing, first_new))
    assert read_paths(target) == first_new

    # 2回目: 既存 3 件 + 新規 0 件 (sync が「変化なし」だけだったケース)
    second_existing = read_paths(target)
    second_new: list[str] = []
    write_paths(target, merge_paths(second_existing, second_new))

    # 上書きされず、1回目の 3 件が残っていることを確認
    assert read_paths(target) == first_new
