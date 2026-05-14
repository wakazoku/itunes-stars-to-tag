"""starcore.tagging のサポート判定と定数の不変性を検証する。

実ファイル I/O (mutagen 経由の MP3/M4A 書き込み) は環境依存が大きいため、
ここでは「ガード節 (= ファイルを開く前に raise する分岐)」と「テーブル定数」
だけを純粋に検証する。
"""
from __future__ import annotations

import pytest

from starcore.tagging import (
    DRM_PROTECTED,
    ITUNES_TO_POPM,
    MP4_RATING_KEY,
    SUPPORTED_MP3,
    SUPPORTED_MP4,
    UnsupportedExtensionError,
    write_rating,
)


class TestUnsupportedExtensionGuards:
    def test_drm_protected_raises_before_io(self):
        """.m4p (DRM) は実ファイル参照前に弾かれる。"""
        with pytest.raises(UnsupportedExtensionError, match="DRM"):
            write_rating(r"C:\not\exist\dummy.m4p", 60)

    def test_unknown_extension_raises_before_io(self):
        with pytest.raises(UnsupportedExtensionError):
            write_rating(r"C:\not\exist\dummy.flac", 60)

    def test_no_extension_raises_before_io(self):
        with pytest.raises(UnsupportedExtensionError):
            write_rating(r"C:\not\exist\noext", 60)


class TestITunesToPopmMapping:
    def test_is_musicbee_compatible(self):
        """MusicBee / Windows Media Player 標準マッピング。
        意図せぬ書き換えに気づくための回帰テスト。"""
        assert ITUNES_TO_POPM == {
            0: 0,
            20: 1,
            40: 64,
            60: 128,
            80: 196,
            100: 255,
        }

    @pytest.mark.parametrize("rating", [0, 20, 40, 60, 80, 100])
    def test_all_itunes_ratings_have_mapping(self, rating):
        assert rating in ITUNES_TO_POPM


class TestExtensionSets:
    def test_mp3_set(self):
        assert ".mp3" in SUPPORTED_MP3

    def test_mp4_set_covers_aac_alac_audiobook(self):
        assert {".m4a", ".mp4", ".m4b"} <= SUPPORTED_MP4

    def test_m4p_is_in_drm_set(self):
        assert ".m4p" in DRM_PROTECTED

    def test_sets_are_disjoint(self):
        """同じ拡張子が複数の分類に属してはいけない。"""
        assert not SUPPORTED_MP3 & SUPPORTED_MP4
        assert not SUPPORTED_MP3 & DRM_PROTECTED
        assert not SUPPORTED_MP4 & DRM_PROTECTED


class TestMP4RatingKeyConstant:
    def test_is_apple_freeform_atom(self):
        """MusicBee / foobar2000 / Mp3tag が読む業界標準のフリーフォームアトム。"""
        assert MP4_RATING_KEY == "----:com.apple.iTunes:RATING"
