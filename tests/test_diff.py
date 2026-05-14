"""starcore.diff.classify の振る舞いを検証する。"""
from __future__ import annotations

import pytest

from starcore.diff import classify


@pytest.mark.parametrize(
    "prev, current, expected",
    [
        # 未記録 -> 0: 何もすることがない
        (None, 0, "none"),
        # 未記録 -> 1以上: 新規評価
        (None, 60, "new"),
        # 同値: 変化なし
        ({"rating": 60}, 60, "none"),
        # 値変更
        ({"rating": 60}, 80, "modified"),
        # 星外し
        ({"rating": 60}, 0, "removed"),
        # 0->0
        ({"rating": 0}, 0, "none"),
        # 0->値あり: 実質新規
        ({"rating": 0}, 60, "new"),
        # path が一緒に入っている state でも rating だけで判定
        ({"rating": 60, "path": "C:\\foo.mp3"}, 60, "none"),
    ],
)
def test_classify(prev, current, expected):
    assert classify(prev, current) == expected


def test_classify_handles_empty_dict_as_no_record():
    """空 dict (rating キー無し) は「未記録」として扱う。"""
    assert classify({}, 60) == "new"
    assert classify({}, 0) == "none"
