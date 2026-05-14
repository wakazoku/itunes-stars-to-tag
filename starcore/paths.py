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
