"""sync_ratings.py

iTunes (Windows) -> MP3 / M4A の物理タグへ星評価を書き込む。
差分のみを検出して書き込み、変更ファイル一覧 (``changed_files.txt``) を出力する。

Usage:
    py sync_ratings.py             # 差分のみ書き込み
    py sync_ratings.py --dry-run   # 書き込みせず差分を表示
    py sync_ratings.py --force-all # state を無視して全評価曲を書き直す
"""
from __future__ import annotations

import os
import argparse
import logging
from pathlib import Path

import win32com.client
from tqdm import tqdm

from starcore import aggregate
from starcore import diff
from starcore import display
from starcore import state as state_mod
from starcore import tagging

# iTunes COM API enum
ITTrackKindFile = 1
ITRatingKindUser = 0

LOG_FILE = "sync_log.txt"
STATE_FILE = "sync_state.json"
CHANGED_FILE = "changed_files.txt"


def main() -> None:
    display.init_console_for_utf8()
    parser = argparse.ArgumentParser(
        description="iTunes -> 物理タグ同期 (差分のみ書き込み)"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="書き込みはせず、差分対象だけ表示")
    parser.add_argument("--limit", type=int, default=0,
                        help="差分が指定件数に達した時点で停止する (0で無制限)")
    parser.add_argument("--force-all", action="store_true",
                        help="state を無視して全評価曲を書き直す (state は新たに上書き)")
    parser.add_argument("--changed-out", type=str, default=CHANGED_FILE,
                        help=f"変更ファイル一覧の出力先 (既定: {CHANGED_FILE})")
    parser.add_argument("--detail", action="store_true",
                        help="rating の遷移マップ (★n -> ★m が何曲) も表示する")
    args = parser.parse_args()

    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        encoding="utf-8",
    )

    state_path = Path(STATE_FILE)
    state = state_mod.load(state_path)
    state_size_before = len(state)
    if args.force_all:
        # --force-all は「state を作り直す」のが意図なので、開始時点で空にする。
        # 既存 state は state_mod.save 時に上書きされる (バックアップは取らない)。
        state = {}

    title = "iTunes → ファイルタグ 同期"
    if args.dry_run:
        title += "  (dry-run)"
    elif args.force_all:
        title += "  (force-all)"
    display.print_header(title)

    if args.force_all:
        print(f"   force-all: state ({state_size_before:,} 件) をリセットして全評価曲を書き直します")
    else:
        print(f"   state 読込:      {state_size_before:,} 件")

    print("   iTunes に接続中... (起動していなければ自動起動します)")
    itunes = win32com.client.Dispatch("iTunes.Application")
    tracks = itunes.LibraryPlaylist.Tracks
    total = tracks.Count
    print(f"   対象ライブラリ:  {total:,} 曲")
    print()

    stats = {
        "new": 0, "modified": 0, "removed": 0,
        "none": 0, "skipped": 0, "failed": 0,
    }
    by_ext: dict[str, int] = {}
    by_star: dict[int, int] = {}                       # 書き込み後の星別件数 (rating>0 のみ)
    transitions: dict[tuple, int] = {}                 # (prev_rating, new_rating) -> 件数
    changed_paths: list[str] = []

    try:
        for i in tqdm(range(1, total + 1), desc="sync", unit="track"):
            try:
                track = tracks.Item(i)

                if track.Kind != ITTrackKindFile:
                    stats["skipped"] += 1
                    continue
                if track.RatingKind != ITRatingKindUser:
                    stats["skipped"] += 1
                    continue

                rating = track.Rating
                pid_high = itunes.ITObjectPersistentIDHigh(track)
                pid_low = itunes.ITObjectPersistentIDLow(track)
                pid = f"{pid_high}_{pid_low}"

                path = track.Location
                if not path or not os.path.exists(path):
                    if rating > 0:
                        logging.warning(f"path-missing: {track.Name} :: {path}")
                    stats["skipped"] += 1
                    continue

                ext = Path(path).suffix.lower()
                if ext in tagging.DRM_PROTECTED:
                    stats["skipped"] += 1
                    continue
                if ext not in tagging.SUPPORTED_MP3 and ext not in tagging.SUPPORTED_MP4:
                    stats["skipped"] += 1
                    continue

                if args.force_all:
                    verdict = "new" if rating > 0 else "none"
                else:
                    verdict = diff.classify(state.get(pid), rating)

                if verdict == "none":
                    stats["none"] += 1
                    continue

                # 集計用に state 更新前の rating を取得しておく (--force-all 時は不明なので None)
                prev_rating = None
                if not args.force_all:
                    prev_entry = state.get(pid)
                    if prev_entry is not None:
                        prev_rating = prev_entry.get("rating")

                if args.dry_run:
                    tqdm.write(f"[dry-run] {verdict:<8} {rating // 20}star {ext} {track.Name}")
                else:
                    tagging.write_rating(path, rating)
                    if rating > 0:
                        state[pid] = {"rating": rating, "path": path}
                    else:
                        state.pop(pid, None)

                changed_paths.append(path)
                stats[verdict] += 1
                by_ext[ext] = by_ext.get(ext, 0) + 1
                if rating > 0:
                    star = rating // 20
                    by_star[star] = by_star.get(star, 0) + 1
                if args.detail:
                    key = (prev_rating, rating)
                    transitions[key] = transitions.get(key, 0) + 1

                changed_total = stats["new"] + stats["modified"] + stats["removed"]
                if args.limit > 0 and changed_total >= args.limit:
                    tqdm.write(f"\n[limit] {args.limit} 件到達のため停止します")
                    break

            except Exception as e:
                stats["failed"] += 1
                logging.error(f"failed[{i}]: {e}")

    finally:
        if not args.dry_run:
            state_mod.save(state_path, state)
            Path(args.changed_out).write_text(
                "\n".join(changed_paths) + ("\n" if changed_paths else ""),
                encoding="utf-8",
            )

    changed_total = stats["new"] + stats["modified"] + stats["removed"]
    result_label = "書き込み予定:" if args.dry_run else "書き込み成功:"
    print()
    display.print_line(display.status_mark(changed_total, "result"),
                       result_label, changed_total)
    display.print_tree_line("新規評価:", stats["new"])
    display.print_tree_line("評価変更:", stats["modified"])
    display.print_tree_line("評価削除:", stats["removed"], last=True)
    display.print_line(display.NEUTRAL_MARK, "変化なし:", stats["none"])
    display.print_line(display.NEUTRAL_MARK, "対象外:", stats["skipped"],
                       note="未評価・自動評価・クラウド等")
    display.print_line(display.status_mark(stats["failed"], "error"),
                       "失敗:", stats["failed"])

    nonzero_stars = sorted((s, n) for s, n in by_star.items() if n > 0)
    if nonzero_stars:
        breakdown_title = "書き込み内訳 (星別) [予定]" if args.dry_run else "書き込み内訳 (星別)"
        print()
        print(f"{breakdown_title}:")
        for star, n in nonzero_stars:
            label = f"★{star}"
            print(f"   {display.pad_display(label, 6)}{display.fmt_count(n)} 曲")

    if args.detail and transitions:
        print()
        print("詳細 (rating 遷移):")
        sorted_keys = sorted(
            transitions.keys(),
            key=lambda k: ((k[0] if k[0] is not None else -1), (k[1] if k[1] is not None else -1)),
        )
        for key in sorted_keys:
            prev_r, new_r = key
            n = transitions[key]
            prev_lbl = aggregate.star_label(prev_r)
            new_lbl = aggregate.star_label(new_r)
            arrow = f"{display.pad_display(prev_lbl, 4)}→ {new_lbl}"
            note = aggregate.transition_note(aggregate.classify_transition(prev_r, new_r))
            note_part = f"  ({note})" if note else ""
            print(f"   {display.pad_display(arrow, 12)}{display.fmt_count(n)} 曲{note_part}")

    if by_ext:
        print()
        print("形式内訳:")
        for ext, n in sorted(by_ext.items(), key=lambda x: -x[1]):
            print(f"   {ext:<6}{display.fmt_count(n)} 曲")

    print()
    if args.dry_run:
        display.print_kv_section("出力ファイル", [
            (LOG_FILE, "(詳細ログ / dry-run では書き込みなし)"),
        ])
    else:
        display.print_kv_section("出力ファイル", [
            (STATE_FILE, "(差分検知用 state)"),
            (args.changed_out, f"(変更ファイル一覧、{changed_total:,} 行)"),
            (LOG_FILE, "(詳細ログ)"),
        ])
    display.print_footer()


if __name__ == "__main__":
    main()
