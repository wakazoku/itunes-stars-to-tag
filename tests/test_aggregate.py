"""starcore.aggregate のラベル生成と遷移分類を検証する。"""
from __future__ import annotations

import pytest

from starcore.aggregate import (
    classify_transition,
    star_label,
    transition_note,
)


class TestStarLabel:
    @pytest.mark.parametrize(
        "rating, expected",
        [
            (None, "─"),
            (0, "─"),
            (20, "★1"),
            (40, "★2"),
            (60, "★3"),
            (80, "★4"),
            (100, "★5"),
        ],
    )
    def test_label_for_each_rating(self, rating, expected):
        assert star_label(rating) == expected


class TestClassifyTransition:
    @pytest.mark.parametrize(
        "prev, now, expected",
        [
            # 変化なし
            (60, 60, "none"),
            (0, 0, "none"),
            (None, 0, "none"),
            # 新規 (未記録 / 0 → 値あり)
            (None, 60, "new"),
            (0, 80, "new"),
            # 削除 (値あり → 0)
            (60, 0, "removed"),
            (100, 0, "removed"),
            # アップ
            (60, 80, "modified-up"),
            (20, 100, "modified-up"),
            # ダウン
            (80, 60, "modified-down"),
            (100, 20, "modified-down"),
        ],
    )
    def test_classify(self, prev, now, expected):
        assert classify_transition(prev, now) == expected


class TestTransitionNote:
    @pytest.mark.parametrize(
        "kind, expected",
        [
            ("new", "新規"),
            ("modified-up", "アップ"),
            ("modified-down", "ダウン"),
            ("removed", "削除"),
            ("none", ""),
        ],
    )
    def test_note(self, kind, expected):
        assert transition_note(kind) == expected
