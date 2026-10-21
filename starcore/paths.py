"""SRC_ROOT 配下のパスを DST_ROOT 配下の対応パスへ変換するロジック。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union


PathLike = Union[str, os.PathLike]


def to_mirror(src_path: PathLike, src_root: PathLike, dst_root: PathLike) -> Optional[Path]:
    """``src_path`` が ``src_root`` 配下なら、``dst_root`` 配下の対応パスを返す。

    配下でない / 比較に失敗した場合は ``None``。Windows を想定して
    ケース非依存で前方一致を判定する (``os.path.normcase`` を利用)。
    """
    src_norm = _normalize(src_path)
    root_norm = _normalize(src_root)
    dst_root_p = Path(dst_root)

    if src_norm == root_norm:
        # src 自体が root なら、相対パスが空になりミラー先を確定できない
        return None
    sep = os.sep
    if not src_norm.startswith(root_norm + sep):
        return None

    # 比較は正規化済みで行ったが、相対部分は normpath の結果からそのまま切り出す
    src_normpath = os.path.normpath(str(src_path))
    root_normpath = os.path.normpath(str(src_root))
    relative = src_normpath[len(root_normpath):].lstrip("\\/")
    if not relative:
        return None
    return dst_root_p / relative


def _normalize(p: PathLike) -> str:
    """case 非依存・セパレータ統一の比較用文字列を返す。"""
    return os.path.normcase(os.path.normpath(str(p)))


def same_location(a: str, b: str) -> bool:
    """2つのパスが同じファイルを指すか。区切り文字と大小文字の差は無視する。

    iTunes の ``Location`` は実行のたびに区切りや大文字小文字が揺れることがある。
    それを「ファイルが移動した」と誤認しないための比較。
    """
    return _location_key(a) == _location_key(b)


def relocation(prev_path: str | None, current_path: str) -> str:
    """前回記録したパスと現在のパスの関係を返す。

    - ``"same"``:  同じ場所
    - ``"fill"``:  前回パスが空。記録を埋めるだけで、コピー対象にはしない
    - ``"moved"``: 別の場所に移っている
    """
    if not prev_path:
        return "fill"
    if same_location(prev_path, current_path):
        return "same"
    return "moved"


def _location_key(path: str) -> str:
    """Windows のファイルパスを比較用に揃える。OS が Linux でも同じ結果にする。"""
    return str(path).replace("/", "\\").lower()
