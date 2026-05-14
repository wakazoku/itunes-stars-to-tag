"""rating の表示用ラベル生成と遷移分類を担う純粋ロジック。

``sync_ratings.py`` のメインループから「ラベル整形」「遷移種別の判定」を切り出し、
ユニットテスト可能にする。副作用なし、外部依存なし。
"""
from __future__ import annotations

from typing import Literal, Optional


TransitionKind = Literal["new", "modified-up", "modified-down", "removed", "none"]


def star_label(rating: Optional[int]) -> str:
    """iTunes rating (0/20/40/60/80/100/None) を表示用ラベルに変換する。

    - ``None`` または ``0`` → ``"─"`` (未評価 / 削除)
    - ``20`` → ``"★1"``, ``40`` → ``"★2"``, ..., ``100`` → ``"★5"``
    """
    if not rating:
        return "─"
    return f"★{rating // 20}"


def classify_transition(prev: Optional[int], now: int) -> TransitionKind:
    """前回 rating から今回 rating への遷移を 5 分類して返す。

    - ``"new"``:           prev が未記録 / 0 で、now > 0 (新しく星を付けた)
    - ``"modified-up"``:   prev も now も >0 で、now > prev (評価アップ)
    - ``"modified-down"``: prev も now も >0 で、now < prev (評価ダウン)
    - ``"removed"``:       prev > 0 で now == 0 (星を外した)
    - ``"none"``:          値が変わっていない / 両方未評価
    """
    prev_v = prev or 0
    if prev_v == now:
        return "none"
    if prev_v == 0:
        return "new"
    if now == 0:
        return "removed"
    return "modified-up" if now > prev_v else "modified-down"


_NOTE_BY_KIND: dict[TransitionKind, str] = {
    "new": "新規",
    "modified-up": "アップ",
    "modified-down": "ダウン",
    "removed": "削除",
    "none": "",
}


def transition_note(kind: TransitionKind) -> str:
    """遷移種別を日本語の短い注釈にする。``"none"`` は空文字。"""
    return _NOTE_BY_KIND.get(kind, "")
