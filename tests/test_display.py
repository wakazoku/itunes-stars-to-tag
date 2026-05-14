"""starcore.display の表示幅計算・パディング・マーク判定を検証する。"""
from __future__ import annotations

import pytest

from starcore.display import (
    NEUTRAL_MARK,
    NG_MARK,
    OK_MARK,
    WARN_MARK,
    display_width,
    fmt_count,
    pad_display,
    status_mark,
)


class TestDisplayWidth:
    @pytest.mark.parametrize(
        "s, expected",
        [
            ("", 0),
            ("a", 1),
            ("abc", 3),
            ("★", 2),
            ("★4", 3),       # 全角 (★=2) + 半角 (4=1)
            ("曲", 2),
            ("曲数", 4),
            ("★★★", 6),
        ],
    )
    def test_width(self, s, expected):
        assert display_width(s) == expected


class TestPadDisplay:
    def test_pads_ascii_to_target_width(self):
        result = pad_display("abc", 6)
        assert result == "abc   "
        assert display_width(result) == 6

    def test_pads_full_width_correctly(self):
        # 表示幅3 (★+半角1) を 6 にする → 末尾に 3 つ空白
        result = pad_display("★4", 6)
        assert display_width(result) == 6
        assert result.endswith("   ")

    def test_does_not_truncate_when_over(self):
        # すでに幅オーバー (★★★ = 幅6) なら何も足さない
        result = pad_display("★★★", 4)
        assert result == "★★★"

    def test_handles_empty_string(self):
        assert pad_display("", 4) == "    "


class TestFmtCount:
    def test_default_width_right_aligned(self):
        # width=5 が既定
        assert fmt_count(0) == "    0"
        assert fmt_count(849) == "  849"

    def test_thousands_separator(self):
        assert fmt_count(11068) == "11,068"

    def test_custom_width(self):
        assert fmt_count(5, width=3) == "  5"


class TestStatusMark:
    def test_result_always_ok(self):
        """主要カウンタは件数に関わらず常に OK_MARK (情報表示として扱う)。"""
        assert status_mark(0, "result") == OK_MARK
        assert status_mark(100, "result") == OK_MARK

    def test_error_kind_flips_at_nonzero(self):
        """error は 0=OK / 1以上=NG。"""
        assert status_mark(0, "error") == OK_MARK
        assert status_mark(1, "error") == NG_MARK
        assert status_mark(99, "error") == NG_MARK

    def test_warn_kind_flips_at_nonzero(self):
        """warn は 0=OK / 1以上=WARN。"""
        assert status_mark(0, "warn") == OK_MARK
        assert status_mark(1, "warn") == WARN_MARK

    def test_neutral_always_dashes(self):
        assert status_mark(0, "neutral") == NEUTRAL_MARK
        assert status_mark(100, "neutral") == NEUTRAL_MARK

    def test_default_kind_is_result(self):
        # kind 未指定なら "result" として扱われる
        assert status_mark(0) == OK_MARK
        assert status_mark(5) == OK_MARK
