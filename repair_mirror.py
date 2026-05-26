"""repair_mirror.py

sync_state.json と DST_ROOT (MusicBee側) のファイルタグを照合し、
ズレているファイルを検出する。--apply を渡すと、SRC 側のパスを
changed_files.txt に追記して mirror_changed.py で再ミラーできる
状態にする。

想定ユースケース:
  sync_ratings.py が二度連続で走って changed_files.txt が空に
  上書きされてしまい、結果として DST 側へミラーされずに古い
  rating が残った曲を救出する。

Usage:
    py repair_mirror.py                # dry-run (表示のみ)
    py repair_mirror.py --apply        # changed_files.txt に追記
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mutagen.id3 import ID3, ID3NoHeaderError
from mutagen.mp4 import MP4

from starcore import changed_list
from starcore import display
from starcore import state as state_mod
from starcore.paths import to_mirror
from starcore.tagging import (
    ITUNES_TO_POPM,
    MP4_RATING_KEY,
    SUPPORTED_MP3,
    SUPPORTED_MP4,
)

STATE_FILE = "sync_state.json"
CHANGED_FILE = "changed_files.txt"

ENV_SRC_ROOT = "STAR_RATE_SYNC_SRC_ROOT"
ENV_DST_ROOT = "STAR_RATE_SYNC_DST_ROOT"


def read_mp4_rating_value(path: Path) -> int | None:
    """MP4 系から RATING アトムの数値を返す。アトムが無ければ None。"""
    audio = MP4(str(path))
    if MP4_RATING_KEY not in audio:
        return None
    raw = audio[MP4_RATING_KEY][0]
    try:
        return int(bytes(raw).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def read_mp3_popm_value(path: Path) -> int | None:
    """MP3 から POPM の rating (0-255) を返す。フレーム自体が無ければ None。"""
    try:
        tags = ID3(str(path))
    except ID3NoHeaderError:
        return None
    popms = tags.getall("POPM")
    if not popms:
        return None
    return popms[0].rating


def compare_dst_with_state(dst_path: Path, ext: str, state_rating: int) -> tuple[str, str]:
    """DST 側ファイルが state_rating と一致しているか調べる。

    Returns:
        (status, detail)
        status: "match" / "mismatch" / "no_tag" / "error"
    """
    try:
        if ext in SUPPORTED_MP4:
            v = read_mp4_rating_value(dst_path)
            if v is None:
                if state_rating == 0:
                    return ("match", "no atom (state=0)")
                return ("no_tag", "RATING atom not found")
            if v == state_rating:
                return ("match", f"rating={v}")
            return ("mismatch", f"dst={v} state={state_rating}")
        if ext in SUPPORTED_MP3:
            v = read_mp3_popm_value(dst_path)
            expected_popm = ITUNES_TO_POPM.get(state_rating, 0)
            if v is None:
                if state_rating == 0:
                    return ("match", "no popm (state=0)")
                return ("no_tag", "POPM frame not found")
            if v == expected_popm:
                return ("match", f"popm={v}")
            return ("mismatch", f"dst_popm={v} expected_popm={expected_popm} (state={state_rating})")
        return ("error", f"unsupported ext: {ext}")
    except Exception as e:
        return ("error", f"{type(e).__name__}: {e}")


def main() -> None:
    display.init_console_for_utf8()
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="state と DST 側タグを照合し、ズレを changed_files.txt に追記する"
    )
    parser.add_argument("--state", type=str, default=STATE_FILE,
                        help=f"参照する state ファイル (既定: {STATE_FILE})")
    parser.add_argument("--src-root", type=str, default=None,
                        help=f"SRC_ROOT (未指定なら環境変数 {ENV_SRC_ROOT})")
    parser.add_argument("--dst-root", type=str, default=None,
                        help=f"DST_ROOT (未指定なら環境変数 {ENV_DST_ROOT})")
    parser.add_argument("--changed-out", type=str, default=CHANGED_FILE,
                        help=f"追記先 (既定: {CHANGED_FILE})")
    parser.add_argument("--apply", action="store_true",
                        help="検出結果を changed_files.txt に追記する (既定は dry-run)")
    parser.add_argument("--include-missing", action="store_true",
                        help="DST にファイル自体が存在しない曲も救出対象にする "
                             "(mirror_changed.py --create-missing と合わせて使う)")
    args = parser.parse_args()

    src_root = args.src_root or os.environ.get(ENV_SRC_ROOT)
    dst_root = args.dst_root or os.environ.get(ENV_DST_ROOT)
    if not src_root or not dst_root:
        print("[error] SRC_ROOT / DST_ROOT が指定されていません。")
        sys.exit(2)

    state_path = Path(args.state)
    if not state_path.exists():
        print(f"[error] {state_path} が見つかりません。")
        sys.exit(1)

    state = state_mod.load(state_path)

    title = "ミラー差分の救出"
    if not args.apply:
        title += "  (dry-run)"
    display.print_header(title)
    print(f"   state:   {len(state):,} 件")
    print(f"   SRC:     {src_root}")
    print(f"   DST:     {dst_root}")
    if args.include_missing:
        print("   mode:    --include-missing (DST に無い曲も救出対象)")
    print()

    stats = {
        "match": 0,
        "mismatch": 0,
        "no_tag": 0,
        "no_dst_file": 0,
        "out_of_src_root": 0,
        "src_missing": 0,
        "error": 0,
    }
    mismatch_examples: list[str] = []
    missing_examples: list[str] = []
    src_paths_to_repair: list[str] = []

    for pid, entry in state.items():
        rating = entry.get("rating", 0)
        src_str = entry.get("path", "")
        src_path = Path(src_str)
        ext = src_path.suffix.lower()

        if not src_path.exists():
            stats["src_missing"] += 1
            continue

        dst_path = to_mirror(src_path, src_root, dst_root)
        if dst_path is None:
            stats["out_of_src_root"] += 1
            continue
        if not dst_path.exists():
            stats["no_dst_file"] += 1
            # --include-missing が指定されている時は「DST にまだ無い曲」も
            # 救出対象としてリストに含める。mirror_changed.py 側で
            # --create-missing を併用すれば、親フォルダごと作って新規コピーされる。
            if args.include_missing and rating > 0:
                src_paths_to_repair.append(str(src_path))
                if len(missing_examples) < 20:
                    star = rating // 20
                    missing_examples.append(
                        f"  [missing] ★{star}  {dst_path.relative_to(dst_root)}"
                    )
            continue

        status, detail = compare_dst_with_state(dst_path, ext, rating)
        stats[status] = stats.get(status, 0) + 1

        if status in ("mismatch", "no_tag"):
            src_paths_to_repair.append(str(src_path))
            if len(mismatch_examples) < 20:
                mismatch_examples.append(
                    f"  [{status}] {dst_path.name}  ({detail})"
                )

    print()
    display.print_line(display.status_mark(stats["match"], "result"),
                       "一致:", stats["match"], suffix="件")
    display.print_line(display.status_mark(stats["mismatch"], "warn"),
                       "不一致:", stats["mismatch"], suffix="件")
    display.print_line(display.status_mark(stats["no_tag"], "warn"),
                       "DSTにタグ無し:", stats["no_tag"], suffix="件")
    display.print_line(display.NEUTRAL_MARK, "DSTにファイル無し:",
                       stats["no_dst_file"], suffix="件")
    display.print_line(display.NEUTRAL_MARK, "SRCにファイル無し:",
                       stats["src_missing"], suffix="件")
    display.print_line(display.NEUTRAL_MARK, "SRC_ROOT外:",
                       stats["out_of_src_root"], suffix="件")
    display.print_line(display.status_mark(stats["error"], "error"),
                       "エラー:", stats["error"], suffix="件")

    if mismatch_examples:
        print()
        print("救出対象: タグ不一致 (先頭20件):")
        for line in mismatch_examples:
            print(line)

    if missing_examples:
        print()
        print("救出対象: DST に未コピー (先頭20件):")
        for line in missing_examples:
            print(line)

    shown = len(mismatch_examples) + len(missing_examples)
    if len(src_paths_to_repair) > shown:
        print(f"  ... 他 {len(src_paths_to_repair) - shown} 件")

    repair_total = len(src_paths_to_repair)
    print()

    if not args.apply:
        print(f"dry-run のため {args.changed_out} は変更しません。")
        print(f"本番実行する場合: py repair_mirror.py --apply")
        display.print_footer()
        return

    if repair_total == 0:
        print("救出対象がありません。何もしません。")
        display.print_footer()
        return

    changed_out = Path(args.changed_out)
    existing = changed_list.read_paths(changed_out)
    merged = changed_list.merge_paths(existing, src_paths_to_repair)
    appended = len(merged) - len(existing)
    changed_list.write_paths(changed_out, merged)
    print(f"{args.changed_out} に {appended} 件追記しました "
          f"(既存 {len(existing)} 件 + 追記 {appended} 件 = 合計 {len(merged)} 件)")
    print()
    print("次のステップ:")
    if args.include_missing and stats["no_dst_file"] > 0:
        # 新規コピー対象が含まれる場合は --create-missing が必要
        print("  1) py mirror_changed.py --dry-run --create-missing   # 確認")
        print("  2) py mirror_changed.py --create-missing             # 実コピー")
    else:
        print("  1) py mirror_changed.py --dry-run   # 何をコピーするか確認")
        print("  2) py mirror_changed.py             # 実コピー")
    print("  3) MusicBee でライブラリ再スキャン")
    display.print_footer()


if __name__ == "__main__":
    main()
