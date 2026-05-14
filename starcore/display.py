"""CLI 出力を整形するための共通ヘルパー。

「成功」「中立」「異常」を絵文字付きで一目で読めるサマリを提供する。
依存追加なしで動く (標準ライブラリのみ)。
"""
from __future__ import annotations

import sys
import unicodedata
from typing import Iterable, Optional, Tuple


def display_width(s: str) -> int:
    """端末表示上の幅 (全角=2 / 半角=1) を計算する。

    East Asian Width が ``A`` (Ambiguous) の文字 (``★``, ``─`` など) は、
    日本語環境のターミナルでは通常全角扱いされるため、ここでも 2 とみなす。
    """
    return sum(
        2 if unicodedata.east_asian_width(c) in ("F", "W", "A") else 1
        for c in s
    )


def pad_display(s: str, width: int) -> str:
    """表示幅で左寄せパディング。全角混在文字列でも数字位置が揃う。"""
    diff = width - display_width(s)
    return s + " " * max(diff, 0)


def init_console_for_utf8() -> None:
    """Windows のコンソール (cp932) では絵文字が UnicodeEncodeError になるため、
    stdout / stderr を UTF-8 に切り替える。Python 3.7+ で利用可能。

    各 CLI エントリポイントの ``main()`` 冒頭で呼ぶことを想定している。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            # reconfigure 非対応な実行環境では諦める (Python 3.6 以下など)
            pass

HBAR = "=" * 60

# 状態マーク
OK_MARK = "✅"
NG_MARK = "❌"
WARN_MARK = "⚠️ "  # U+26A0 + VS16 で見た目を絵文字に寄せる場合のスペース調整
NEUTRAL_MARK = "──"


def print_header(title: str) -> None:
    print(HBAR)
    print(f"  {title}")
    print(HBAR)


def print_footer() -> None:
    print(HBAR)


def status_mark(count: int, kind: str = "result") -> str:
    """件数とカテゴリから状態マークを返す。

    - kind="result":  count >= 0 で常に ``OK_MARK`` (主な成功カウンタ用)
    - kind="error":   count == 0 → OK / >0 → NG (失敗・エラー用)
    - kind="warn":    count == 0 → OK / >0 → WARN (mismatch 等の注意系)
    - kind="neutral": 常に ``NEUTRAL_MARK`` (情報系)
    """
    if kind == "neutral":
        return NEUTRAL_MARK
    if kind == "error":
        return NG_MARK if count > 0 else OK_MARK
    if kind == "warn":
        return WARN_MARK if count > 0 else OK_MARK
    return OK_MARK


def fmt_count(count: int, width: int = 5) -> str:
    """3桁区切りで右寄せした件数文字列。"""
    return f"{count:>{width},}"


_LABEL_WIDTH = 16
_TREE_LABEL_WIDTH = 16
_KEY_WIDTH = 24


def print_line(mark: str, label: str, count: int, suffix: str = "曲", note: Optional[str] = None) -> None:
    """1 行のサマリを出す。

    例:  ``✅ 書き込み成功:     849 曲``
    note を渡すと右側に ``(...)`` で補足を表示する。
    """
    base = f"{mark} {pad_display(label, _LABEL_WIDTH)}{fmt_count(count)} {suffix}"
    if note:
        base += f"  ({note})"
    print(base)


def print_tree_line(label: str, count: int, suffix: str = "曲", last: bool = False) -> None:
    """ツリー風のサブ項目を表示。

    例:  ``   ├─ 新規評価:        1 曲``
         ``   └─ 評価変更:        2 曲``
    """
    branch = "└─" if last else "├─"
    print(f"   {branch} {pad_display(label, _TREE_LABEL_WIDTH)}{fmt_count(count)} {suffix}")


def print_kv_section(title: str, items: Iterable[Tuple[str, str]]) -> None:
    """「タイトル + key: value のリスト」を出す。出力ファイル一覧などに使う。

    例:
        出力ファイル:
           sync_state.json      (差分検知用 state)
    """
    print(f"{title}:")
    for key, value in items:
        print(f"   {pad_display(key, _KEY_WIDTH)}{value}")
