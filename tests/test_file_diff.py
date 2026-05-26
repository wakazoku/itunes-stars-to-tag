"""starcore.file_diff の走査・比較ロジックを検証する。

実ファイルを tmp_path に作って、走査 & 比較が
new / updated / same / orphan を正しく分類することを確認する。
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from starcore.file_diff import (
    DEFAULT_EXTENSIONS,
    DEFAULT_MTIME_TOLERANCE_SEC,
    DiffResult,
    FileEntry,
    compare_trees,
    is_same_content,
    scan_tree,
)


# ---------------------------------------------------------------------------
# 小道具
# ---------------------------------------------------------------------------
def _touch(path: Path, content: bytes = b"x", mtime: float | None = None) -> None:
    """テスト用にファイルを作って (必要なら) mtime を上書きする。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


# ---------------------------------------------------------------------------
# scan_tree
# ---------------------------------------------------------------------------
def test_scan_tree_missing_root_returns_empty(tmp_path: Path):
    assert scan_tree(tmp_path / "does_not_exist") == {}


def test_scan_tree_walks_recursively(tmp_path: Path):
    _touch(tmp_path / "a.mp3", b"a")
    _touch(tmp_path / "sub" / "b.m4a", b"bb")
    _touch(tmp_path / "sub" / "deep" / "c.mp3", b"ccc")
    result = scan_tree(tmp_path)
    assert set(result.keys()) == {"a.mp3", "sub\\b.m4a", "sub\\deep\\c.mp3"}


def test_scan_tree_filters_by_extension(tmp_path: Path):
    _touch(tmp_path / "song.mp3")
    _touch(tmp_path / "cover.jpg")
    _touch(tmp_path / "notes.txt")
    _touch(tmp_path / "movie.mp4")
    result = scan_tree(tmp_path)
    assert set(result.keys()) == {"song.mp3", "movie.mp4"}


def test_scan_tree_custom_extensions(tmp_path: Path):
    _touch(tmp_path / "a.flac")
    _touch(tmp_path / "b.mp3")
    result = scan_tree(tmp_path, extensions=[".flac"])
    assert set(result.keys()) == {"a.flac"}


def test_scan_tree_normalizes_extension_input(tmp_path: Path):
    """拡張子は ".ext" 小文字に正規化される (キーも大小無視で小文字化)。"""
    _touch(tmp_path / "a.FLAC")
    _touch(tmp_path / "b.mp3")
    result = scan_tree(tmp_path, extensions=["FLAC", ".Mp3"])
    # キーは小文字化されるが、FileEntry.relative には元のファイル名が保たれる。
    assert set(result.keys()) == {"a.flac", "b.mp3"}
    assert result["a.flac"].relative.name == "a.FLAC"


def test_scan_tree_records_size_and_mtime(tmp_path: Path):
    p = tmp_path / "x.mp3"
    _touch(p, b"hello world", mtime=1_700_000_000.0)
    entry = scan_tree(tmp_path)["x.mp3"]
    assert entry.size == len(b"hello world")
    assert entry.mtime == pytest.approx(1_700_000_000.0, abs=1e-3)


def test_default_extensions_cover_supported_audio_formats():
    assert ".mp3" in DEFAULT_EXTENSIONS
    assert ".m4a" in DEFAULT_EXTENSIONS
    assert ".m4b" in DEFAULT_EXTENSIONS
    assert ".mp4" in DEFAULT_EXTENSIONS


# ---------------------------------------------------------------------------
# is_same_content
# ---------------------------------------------------------------------------
def test_is_same_content_size_mismatch_means_different():
    a = FileEntry(Path("a"), size=10, mtime=100.0)
    b = FileEntry(Path("a"), size=11, mtime=100.0)
    assert is_same_content(a, b) is False


def test_is_same_content_mtime_within_tolerance_is_same():
    a = FileEntry(Path("a"), size=10, mtime=100.0)
    b = FileEntry(Path("a"), size=10, mtime=100.5)
    # 既定許容は 1 秒
    assert is_same_content(a, b) is True


def test_is_same_content_mtime_outside_tolerance_is_different():
    a = FileEntry(Path("a"), size=10, mtime=100.0)
    b = FileEntry(Path("a"), size=10, mtime=110.0)
    assert is_same_content(a, b) is False


def test_is_same_content_custom_tolerance():
    a = FileEntry(Path("a"), size=10, mtime=100.0)
    b = FileEntry(Path("a"), size=10, mtime=104.0)
    assert is_same_content(a, b, tolerance_sec=5.0) is True
    assert is_same_content(a, b, tolerance_sec=2.0) is False


# ---------------------------------------------------------------------------
# compare_trees
# ---------------------------------------------------------------------------
def _entry(rel: str, size: int = 10, mtime: float = 100.0) -> FileEntry:
    return FileEntry(relative=Path(rel), size=size, mtime=mtime)


def test_compare_trees_classifies_into_four_buckets():
    src = {
        "a.mp3": _entry("a.mp3", size=10, mtime=100.0),                # same
        "b.mp3": _entry("b.mp3", size=20, mtime=200.0),                # updated (size)
        "c.mp3": _entry("c.mp3", size=30, mtime=300.0),                # new
    }
    dst = {
        "a.mp3": _entry("a.mp3", size=10, mtime=100.0),                # same
        "b.mp3": _entry("b.mp3", size=21, mtime=200.0),                # size 違い
        "z.mp3": _entry("z.mp3", size=99, mtime=999.0),                # orphan
    }
    result = compare_trees(src, dst)
    assert [e.relative.name for e in result.same] == ["a.mp3"]
    assert [e.relative.name for e in result.updated] == ["b.mp3"]
    assert [e.relative.name for e in result.new] == ["c.mp3"]
    assert [e.relative.name for e in result.orphan] == ["z.mp3"]


def test_compare_trees_updated_when_mtime_outside_tolerance():
    src = {"a.mp3": _entry("a.mp3", size=10, mtime=100.0)}
    dst = {"a.mp3": _entry("a.mp3", size=10, mtime=130.0)}
    result = compare_trees(src, dst)
    assert [e.relative.name for e in result.updated] == ["a.mp3"]
    assert result.same == []


def test_compare_trees_same_when_within_tolerance():
    src = {"a.mp3": _entry("a.mp3", size=10, mtime=100.0)}
    dst = {"a.mp3": _entry("a.mp3", size=10, mtime=100.7)}
    result = compare_trees(src, dst)
    assert [e.relative.name for e in result.same] == ["a.mp3"]
    assert result.updated == []


def test_compare_trees_empty_inputs():
    result = compare_trees({}, {})
    assert result.new == []
    assert result.updated == []
    assert result.same == []
    assert result.orphan == []


def test_compare_trees_results_are_sorted_by_key():
    src = {
        "z.mp3": _entry("z.mp3"),
        "a.mp3": _entry("a.mp3"),
        "m.mp3": _entry("m.mp3"),
    }
    dst: dict[str, FileEntry] = {}
    result = compare_trees(src, dst)
    assert [e.relative.name for e in result.new] == ["a.mp3", "m.mp3", "z.mp3"]


def test_diff_result_totals():
    src = {
        "a.mp3": _entry("a.mp3", size=10, mtime=100.0),  # same
        "b.mp3": _entry("b.mp3", size=10, mtime=100.0),  # new
    }
    dst = {
        "a.mp3": _entry("a.mp3", size=10, mtime=100.0),  # same
        "z.mp3": _entry("z.mp3"),                        # orphan
    }
    result = compare_trees(src, dst)
    assert result.total_scanned_src() == 2
    assert result.total_scanned_dst() == 2


# ---------------------------------------------------------------------------
# scan_tree + compare_trees の結合シナリオ
# ---------------------------------------------------------------------------
def test_scan_and_compare_end_to_end(tmp_path: Path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"

    _touch(src / "Artist" / "Album" / "01 same.mp3", b"aaa", mtime=1_700_000_000.0)
    _touch(src / "Artist" / "Album" / "02 updated.mp3", b"bbbb", mtime=1_700_000_500.0)
    _touch(src / "Artist" / "Album" / "03 new.mp3", b"ccccc", mtime=1_700_001_000.0)

    _touch(dst / "Artist" / "Album" / "01 same.mp3", b"aaa", mtime=1_700_000_000.0)
    _touch(dst / "Artist" / "Album" / "02 updated.mp3", b"bbbb", mtime=1_700_000_999.0)
    _touch(dst / "Artist" / "Album" / "99 orphan.mp3", b"xx", mtime=1_700_000_000.0)

    src_map = scan_tree(src)
    dst_map = scan_tree(dst)
    result = compare_trees(src_map, dst_map)

    assert [e.relative.name for e in result.same] == ["01 same.mp3"]
    assert [e.relative.name for e in result.updated] == ["02 updated.mp3"]
    assert [e.relative.name for e in result.new] == ["03 new.mp3"]
    assert [e.relative.name for e in result.orphan] == ["99 orphan.mp3"]
