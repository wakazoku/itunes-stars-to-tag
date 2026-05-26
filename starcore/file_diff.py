"""SRC_ROOT と DST_ROOT のファイル一覧を mtime + size で比較するロジック。

`sync_files.py` から利用される純粋ロジック。
評価 (rating) には一切触れず、ファイル本体の差分だけを扱う。

判定:
    new      : SRC にあり、DST に同名ファイルが無い
    updated  : 両方にあるが、mtime か size が異なる (= 中身が変わった疑い)
    same     : 両方にあって mtime と size が一致 (= 変更なし)
    orphan   : DST にあり、SRC に同名ファイルが無い
               (DST 側だけに残った曲。削除は行わずレポートのみ。)

判定対象は ``extensions`` で指定された拡張子のみ。
既定では音声ファイル系のみを対象にする。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional


# 既定の対象拡張子。リポジトリ全体の方針 (MP3 / M4A / MP4 / M4B) と揃える。
# 大文字小文字は無視するため、すべて小文字で持っておく。
DEFAULT_EXTENSIONS = frozenset({".mp3", ".m4a", ".m4b", ".mp4"})

# mtime 比較の許容誤差 (秒)。FAT32 等は 2 秒精度なので 1 秒は欲しい。
# shutil.copy2 は mtime を保存するため通常は 0 でも問題ないが、
# 異なるファイルシステムをまたいだコピーの安全マージンとして 1 秒を採用。
DEFAULT_MTIME_TOLERANCE_SEC = 1.0


@dataclass(frozen=True)
class FileEntry:
    """走査結果の 1 ファイル分。

    - ``relative``: ルートからの相対パス (Path)。比較キーは ``normcase(str)``。
    - ``size``:     バイト数
    - ``mtime``:    最終更新時刻 (UNIX 時刻)
    """
    relative: Path
    size: int
    mtime: float


@dataclass
class DiffResult:
    """``compare_trees`` の戻り値。

    各リストの中身は ``FileEntry``。``new`` と ``updated`` は SRC 側起点、
    ``orphan`` は DST 側起点。
    """
    new: list[FileEntry] = field(default_factory=list)
    updated: list[FileEntry] = field(default_factory=list)
    same: list[FileEntry] = field(default_factory=list)
    orphan: list[FileEntry] = field(default_factory=list)

    def total_scanned_src(self) -> int:
        return len(self.new) + len(self.updated) + len(self.same)

    def total_scanned_dst(self) -> int:
        return len(self.updated) + len(self.same) + len(self.orphan)


def _normalize_extensions(extensions: Optional[Iterable[str]]) -> frozenset[str]:
    """ユーザー指定の拡張子セットを ".ext" の小文字に揃える。"""
    if extensions is None:
        return DEFAULT_EXTENSIONS
    out: set[str] = set()
    for e in extensions:
        if not e:
            continue
        e = e.lower()
        if not e.startswith("."):
            e = "." + e
        out.add(e)
    return frozenset(out)


def scan_tree(root: Path, extensions: Optional[Iterable[str]] = None) -> dict[str, FileEntry]:
    """``root`` 配下を再帰的に走査し、対象拡張子のファイル一覧を返す。

    キーは「ルートからの相対パスを Windows 風に正規化した文字列」(大小無視)。
    値は ``FileEntry``。``root`` が存在しなければ空 dict を返す。
    """
    exts = _normalize_extensions(extensions)
    result: dict[str, FileEntry] = {}
    if not root.exists():
        return result

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in exts:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        relative = path.relative_to(root)
        key = _rel_key(relative)
        result[key] = FileEntry(relative=relative, size=stat.st_size, mtime=stat.st_mtime)
    return result


def _rel_key(relative: Path) -> str:
    """相対パスを「比較用の文字列キー」に変換する。

    Windows のファイル名は大小無視 + パス区切りは ``\\`` に統一して扱う。
    """
    # PurePath はプラットフォーム依存だが、Windows 想定なので backslash で OK。
    # 念のため正規化 (\\ に統一) して lower() する。
    s = str(relative).replace("/", "\\")
    return s.lower()


def is_same_content(src: FileEntry, dst: FileEntry,
                    tolerance_sec: float = DEFAULT_MTIME_TOLERANCE_SEC) -> bool:
    """size 一致 & mtime が許容範囲内なら「中身は同じ」とみなす。"""
    if src.size != dst.size:
        return False
    return abs(src.mtime - dst.mtime) <= tolerance_sec


def compare_trees(
    src_map: dict[str, FileEntry],
    dst_map: dict[str, FileEntry],
    tolerance_sec: float = DEFAULT_MTIME_TOLERANCE_SEC,
) -> DiffResult:
    """SRC と DST の走査結果を突き合わせて、new / updated / same / orphan に分類する。

    並び順はキーのソート順 (= 相対パスの辞書順, 大小無視)。
    """
    result = DiffResult()
    src_keys = set(src_map.keys())
    dst_keys = set(dst_map.keys())

    only_src = sorted(src_keys - dst_keys)
    only_dst = sorted(dst_keys - src_keys)
    both = sorted(src_keys & dst_keys)

    for k in only_src:
        result.new.append(src_map[k])
    for k in only_dst:
        result.orphan.append(dst_map[k])
    for k in both:
        src_entry = src_map[k]
        dst_entry = dst_map[k]
        if is_same_content(src_entry, dst_entry, tolerance_sec=tolerance_sec):
            result.same.append(src_entry)
        else:
            result.updated.append(src_entry)
    return result
