"""sync_state.json の読み書きを担当するモジュール。

state 形式:
    {
      "<pid_high>_<pid_low>": { "rating": <int>, "path": "<absolute path>" },
      ...
    }

JSON が壊れていた場合は ``<file>.broken`` にリネームして空 state で復旧する
(=「state が壊れて止まる」を防ぐ)。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


State = Dict[str, dict]


def load(path: Path) -> State:
    """state ファイルを読み込む。存在しない/壊れている場合は空 dict を返す。"""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        backup = path.with_name(path.name + ".broken")
        path.replace(backup)
        print(f"[warn] state が破損していたためバックアップへ退避: {backup}")
        return {}

    if not isinstance(data, dict):
        backup = path.with_name(path.name + ".broken")
        path.replace(backup)
        print(f"[warn] state の形式が不正だったためバックアップへ退避: {backup}")
        return {}
    return data


def save(path: Path, state: State) -> None:
    """state ファイルを書き込む (UTF-8 / 2 スペースインデント)。"""
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
