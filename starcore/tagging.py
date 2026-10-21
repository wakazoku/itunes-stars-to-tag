"""音楽ファイルの物理タグへ星評価を書き込むモジュール。"""

from __future__ import annotations

from pathlib import Path

from mutagen.id3 import ID3, POPM, ID3NoHeaderError
from mutagen.mp4 import MP4, MP4FreeForm


# MusicBee / Windows Media Player 互換マッピング
ITUNES_TO_POPM = {0: 0, 20: 1, 40: 64, 60: 128, 80: 196, 100: 255}

SUPPORTED_MP3 = {".mp3"}
SUPPORTED_MP4 = {".m4a", ".mp4", ".m4b"}
DRM_PROTECTED = {".m4p"}

MP4_RATING_KEY = "----:com.apple.iTunes:RATING"


class UnsupportedExtensionError(ValueError):
    """サポート外 / DRM 保護されたファイルに書き込もうとした場合。"""


class UnsupportedRatingError(ValueError):
    """半星など、0/20/40/60/80/100 以外の評価を書き込もうとした場合。"""


def is_supported_rating(rating: int) -> bool:
    """iTunes の整数評価が、このツールの書き込み対象か。

    対応するのは未評価 (0) と ★1〜★5 (20, 40, 60, 80, 100) だけ。
    半星 (10, 30, 50, 70, 90) は POPM に対応する値がないため対象外。
    """
    return rating in ITUNES_TO_POPM


def _require_supported_rating(rating: int) -> None:
    if not is_supported_rating(rating):
        raise UnsupportedRatingError(
            f"半星など未対応の評価です: {rating} (対応は 0, 20, 40, 60, 80, 100)"
        )


def write_rating(path: str, rating: int) -> None:
    """拡張子に応じて適切なフォーマットで rating を書き込む。

    rating が 0 のときは「未評価」として該当タグを削除する。
    """
    ext = Path(path).suffix.lower()
    if ext in DRM_PROTECTED:
        raise UnsupportedExtensionError(f"DRM 保護されたファイルは書き込めません: {path}")
    if ext in SUPPORTED_MP3:
        write_mp3_rating(path, rating)
        return
    if ext in SUPPORTED_MP4:
        write_mp4_rating(path, rating)
        return
    raise UnsupportedExtensionError(f"サポート外の拡張子です: {ext}")


def write_mp3_rating(path: str, rating: int) -> None:
    """MP3 に POPM フレームで rating を書き込む。rating=0 では POPM を削除する。"""
    _require_supported_rating(rating)
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    tags.delall("POPM")
    if rating > 0:
        popm_value = ITUNES_TO_POPM.get(rating, 0)
        tags.add(POPM(email="no@email", rating=popm_value, count=0))
    tags.save(path, v2_version=3)


def write_mp4_rating(path: str, rating: int) -> None:
    """M4A/MP4 にフリーフォームアトムで rating を書き込む。rating=0 ではアトムを削除する。"""
    _require_supported_rating(rating)
    audio = MP4(path)
    if rating > 0:
        audio[MP4_RATING_KEY] = [
            MP4FreeForm(str(rating).encode("utf-8"), dataformat=MP4FreeForm.FORMAT_TEXT)
        ]
    elif MP4_RATING_KEY in audio:
        del audio[MP4_RATING_KEY]
    audio.save()
