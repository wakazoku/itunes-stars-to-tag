"""starcore.state の読み書きと壊れた JSON への耐性を検証する。"""
from __future__ import annotations

import json
from pathlib import Path

from starcore import state as state_mod


def test_load_nonexistent_returns_empty(tmp_path: Path):
    path = tmp_path / "missing.json"
    assert state_mod.load(path) == {}


def test_save_then_load_round_trip(tmp_path: Path):
    path = tmp_path / "state.json"
    data = {
        "pid_A": {"rating": 80, "path": r"C:\Music\a.mp3"},
        "pid_B": {"rating": 60, "path": r"C:\Music\b.m4a"},
    }
    state_mod.save(path, data)
    loaded = state_mod.load(path)
    assert loaded == data


def test_save_preserves_unicode(tmp_path: Path):
    """日本語の曲名・パスでも壊れない (ensure_ascii=False の確認)。"""
    path = tmp_path / "state.json"
    data = {"pid": {"rating": 100, "path": r"C:\音楽\テスト曲.mp3"}}
    state_mod.save(path, data)
    raw = path.read_text(encoding="utf-8")
    assert "音楽" in raw
    assert state_mod.load(path) == data


def test_broken_json_is_quarantined(tmp_path: Path, capsys):
    """壊れた JSON は .broken にリネームされ、空 state を返す。"""
    path = tmp_path / "state.json"
    path.write_text("{ this is not valid json", encoding="utf-8")

    result = state_mod.load(path)

    assert result == {}
    backup = tmp_path / "state.json.broken"
    assert backup.exists(), "壊れた state は .broken に退避されているはず"
    assert not path.exists(), "元ファイルは退避されてもう存在しないはず"
    captured = capsys.readouterr()
    assert "破損" in captured.out


def test_non_dict_json_is_quarantined(tmp_path: Path, capsys):
    """旧仕様 (PID リスト) や配列形式の JSON も「不正」扱いで退避される。"""
    path = tmp_path / "state.json"
    path.write_text(json.dumps(["pid_A", "pid_B"]), encoding="utf-8")

    result = state_mod.load(path)

    assert result == {}
    backup = tmp_path / "state.json.broken"
    assert backup.exists()
    captured = capsys.readouterr()
    assert "不正" in captured.out
