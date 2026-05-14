"""starcore.paths.to_mirror のパス変換を検証する。"""
from __future__ import annotations

import os

import pytest

from starcore.paths import to_mirror


SRC_ROOT = r"C:\Users\wakaz\Music\iTunes\iTunes Media\Music"
DST_ROOT = r"C:\Users\wakaz\Music\MusicBee\Music"


@pytest.mark.skipif(os.name != "nt", reason="Windows パス前提のテスト")
def test_basic_mapping():
    src = r"C:\Users\wakaz\Music\iTunes\iTunes Media\Music\Artist\Album\song.mp3"
    expected = r"C:\Users\wakaz\Music\MusicBee\Music\Artist\Album\song.mp3"
    result = to_mirror(src, SRC_ROOT, DST_ROOT)
    assert result is not None
    assert str(result) == expected


@pytest.mark.skipif(os.name != "nt", reason="Windows パス前提のテスト")
def test_case_insensitive_root_prefix():
    """SRC_ROOT 部分が大文字小文字違いでもマッチする (Windows のファイルシステム前提)。"""
    src = r"c:\users\wakaz\music\itunes\itunes media\music\Artist\song.mp3"
    result = to_mirror(src, SRC_ROOT, DST_ROOT)
    assert result is not None
    assert str(result).lower().endswith(r"musicbee\music\artist\song.mp3")


@pytest.mark.skipif(os.name != "nt", reason="Windows パス前提のテスト")
def test_outside_src_root_returns_none():
    src = r"C:\Other\Random\Place\song.mp3"
    assert to_mirror(src, SRC_ROOT, DST_ROOT) is None


@pytest.mark.skipif(os.name != "nt", reason="Windows パス前提のテスト")
def test_trailing_separator_in_root_is_tolerated():
    src = r"C:\Users\wakaz\Music\iTunes\iTunes Media\Music\Artist\song.mp3"
    expected_tail = r"MusicBee\Music\Artist\song.mp3"
    result = to_mirror(src, SRC_ROOT + "\\", DST_ROOT)
    assert result is not None
    assert str(result).endswith(expected_tail)


@pytest.mark.skipif(os.name != "nt", reason="Windows パス前提のテスト")
def test_src_equals_root_returns_none():
    """src が root そのものだとミラー先を確定できないので None を返す。"""
    assert to_mirror(SRC_ROOT, SRC_ROOT, DST_ROOT) is None


@pytest.mark.skipif(os.name != "nt", reason="Windows パス前提のテスト")
def test_root_with_forward_slashes_is_normalized():
    src = r"C:\Users\wakaz\Music\iTunes\iTunes Media\Music\Artist\song.mp3"
    result = to_mirror(src, "C:/Users/wakaz/Music/iTunes/iTunes Media/Music", DST_ROOT)
    assert result is not None
    assert str(result).endswith(r"Artist\song.mp3")
