"""sync_routine.py

普段の運用を 1 回で通す。

    1. sync_ratings.py   星評価をファイルタグへ書き込む
    2. sync_files.py     ファイル本体の差分を changed_files.txt に追記する
    3. mirror_changed.py MusicBee 側へコピーする (--create-missing)

既定は dry-run。本番は ``--apply``。
途中の段階が失敗したら、そこで止める。

Usage:
    py sync_routine.py            # 3段階とも dry-run
    py sync_routine.py --apply    # 書き込みとコピーを実行
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from starcore import display
from starcore.routine import run_routine, run_step


def main() -> None:
    display.init_console_for_utf8()
    parser = argparse.ArgumentParser(
        description="評価の書き込み、ファイル差分、ミラーコピーを順に実行する"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="本番実行する (既定は各段階の dry-run)",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    title = "普段の運用"
    if not args.apply:
        title += "  (dry-run)"
    display.print_header(title)
    if args.apply:
        print("   書込 → ファイル差分の追記 → コピー (新規も作成)")
    else:
        print("   3段階とも dry-run。ファイルは変更しません")
    print()

    def runner(argv: list[str], cwd: Path) -> int:
        display.print_header("$ " + " ".join(argv[2:]))
        code = run_step(argv, cwd)
        print()
        if code != 0:
            print(f"[error] {argv[2]} が終了コード {code} で失敗したため中断します")
        return code

    code = run_routine(args.apply, sys.executable, root, runner)
    if code == 0 and not args.apply:
        print("本番実行する場合: py sync_routine.py --apply")
    display.print_footer()
    sys.exit(code)


if __name__ == "__main__":
    main()
