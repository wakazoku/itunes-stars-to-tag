"""星評価の差分判定を行う純粋ロジック。"""

from __future__ import annotations

from typing import Literal, Optional, TypedDict


class StateEntry(TypedDict, total=False):
    rating: int
    path: str


Verdict = Literal["new", "modified", "removed", "none"]


def classify(prev: Optional[StateEntry], current_rating: int) -> Verdict:
    """前回の state エントリと現在の rating から変更分類を返す。

    - "new":       state に記録なし、または前回 0 で、今回 1 以上に評価された
    - "modified":  前回も今回も 1 以上で、値が変わった
    - "removed":   前回 1 以上、今回 0 (=星を外した)
    - "none":      変化なし、または両方 0
    """
    prev_rating = prev.get("rating") if prev else None

    if prev_rating == current_rating:
        return "none"
    if prev_rating is None or prev_rating == 0:
        return "new" if current_rating > 0 else "none"
    if current_rating == 0:
        return "removed"
    return "modified"
