"""sync_files.py

SRC_ROOT (iTunes 側) と DST_ROOT (MusicBee 側) のファイルを比較し、
ファイル本体の差分 (new / updated) を検出する。

評価 (rating) には一切触れない。星が付いていない曲も含めて
「ファイルライブラリ全体」をミラーするためのジョブ。

検出された SRC 側パスは ``changed_files.txt`` に追記される。
あとは ``mirror_changed.py --create-missing`` を実行すれば、
親フォルダ作成 + コピーが行われる (=評価同期と同じパイプライン)。

孤児 (DST 側にあるが SRC に無いファイル) は **削除せずレポートのみ** にする。
意図しない削除を避けるため、削除は手動で行う想定。

Usage:
    py sync_files.py                           # dry-run (検出のみ)
    py sync_files.py --apply                   # changed_files.txt に追記
    py sync_files.py --apply --no-include-new  # 既存ファイルの更新のみ追記
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from starcore import changed_list
from starcore import display
from starcore.file_diff import (
    DEFAULT_MTIME_TOLERANCE_SEC,
    compare_trees,
    scan_tree,
)

CHANGED_FILE = "changed_files.txt"
ORPHAN_LOG_FILE = "orphan_files.txt"

ENV_SRC_ROOT = "STAR_RATE_SYNC_SRC_ROOT"
ENV_DST_ROOT = "STAR_RATE_SYNC_DST_ROOT"


def main() -> None:
    display.init_console_for_utf8()
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="SRC と DST のファイル差分を検出して changed_files.txt に追記する "
                    "(評価は触らない、孤児はレポートのみ)"
    )
    parser.add_argument("--src-root", type=str, default=None,
                        help=f"SRC_ROOT (未指定なら環境変数 {ENV_SRC_ROOT})")
    parser.add_argument("--dst-root", type=str, default=None,
                        help=f"DST_ROOT (未指定なら環境変数 {ENV_DST_ROOT})")
    parser.add_argument("--changed-out", type=str, default=CHANGED_FILE,
                        help=f"追記先 (既定: {CHANGED_FILE})")
    parser.add_argument("--orphan-out", type=str, default=ORPHAN_LOG_FILE,
                        help=f"孤児ファイルのレポート出力先 (既定: {ORPHAN_LOG_FILE})")
    parser.add_argument("--apply", action="store_true",
                        help="検出結果を changed_files.txt に追記する (既定は dry-run)")
    parser.add_argument("--no-include-new", action="store_true",
                        help="DST にまだ無い新規ファイルを追記対象から除外する")
    parser.add_argument("--no-include-updated", action="store_true",
                        help="size/mtime が変わった更新ファイルを追記対象から除外する")
    parser.add_argument("--mtime-tolerance", type=float,
                        default=DEFAULT_MTIME_TOLERANCE_SEC,
                        help=f"mtime 一致とみなす誤差秒数 (既定: {DEFAULT_MTIME_TOLERANCE_SEC})")
    args = parser.parse_args()

    src_root = args.src_root or os.environ.get(ENV_SRC_ROOT)
    dst_root = args.dst_root or os.environ.get(ENV_DST_ROOT)
    if not src_root or not dst_root:
        print("[error] SRC_ROOT / DST_ROOT が指定されていません。")
        print("        以下のいずれかを設定してください:")
        print(f"          - CLI 引数: --src-root <path> --dst-root <path>")
        print(f"          - .env ファイル (cp .env.example .env して編集)")
        print(f"          - 環境変数: {ENV_SRC_ROOT} / {ENV_DST_ROOT}")
        sys.exit(2)

    src_root_path = Path(src_root)
    dst_root_path = Path(dst_root)

    title = "ファイル同期 (mtime+size 差分)"
    if not args.apply:
        title += "  (dry-run)"
    display.print_header(title)
    print(f"   SRC:     {src_root}")
    print(f"   DST:     {dst_root}")
    print(f"   mtime 許容: ±{args.mtime_tolerance:g} 秒")
    print()

    print("   走査中: SRC...")
    src_map = scan_tree(src_root_path)
    print(f"            {len(src_map):,} ファイル")
    print("   走査中: DST...")
    dst_map = scan_tree(dst_root_path)
    print(f"            {len(dst_map):,} ファイル")
    print()

    result = compare_trees(src_map, dst_map, tolerance_sec=args.mtime_tolerance)

    display.print_line(display.NEUTRAL_MARK, "同一:",
                       len(result.same), suffix="件")
    display.print_line(display.status_mark(len(result.new), "warn"),
                       "新規 (DSTに無し):", len(result.new), suffix="件")
    display.print_line(display.status_mark(len(result.updated), "warn"),
                       "更新 (mtime/size 差):", len(result.updated), suffix="件")
    display.print_line(display.status_mark(len(result.orphan), "warn"),
                       "孤児 (SRCに無し):", len(result.orphan), suffix="件",
                       note="レポートのみ、削除はしない")

    # ----- 追記対象の絶対パス一覧を組み立てる -----
    # SRC 側ルートと相対パスから絶対パスに戻す。mirror_changed.py が
    # それを SRC_ROOT -> DST_ROOT に再変換する想定。
    to_append: list[str] = []
    if not args.no_include_new:
        for entry in result.new:
            to_append.append(str(src_root_path / entry.relative))
    if not args.no_include_updated:
        for entry in result.updated:
            to_append.append(str(src_root_path / entry.relative))

    # ----- サンプル表示 (先頭 20 件まで) -----
    if result.new:
        print()
        print("新規 (DSTに無し) サンプル (先頭20件):")
        for entry in result.new[:20]:
            print(f"  + {entry.relative}")
        if len(result.new) > 20:
            print(f"  ... 他 {len(result.new) - 20} 件")
    if result.updated:
        print()
        print("更新 (mtime/size 差) サンプル (先頭20件):")
        for entry in result.updated[:20]:
            print(f"  ~ {entry.relative}")
        if len(result.updated) > 20:
            print(f"  ... 他 {len(result.updated) - 20} 件")
    if result.orphan:
        print()
        print("孤児 (SRCに無し) サンプル (先頭20件) [レポートのみ]:")
        for entry in result.orphan[:20]:
            print(f"  ? {entry.relative}")
        if len(result.orphan) > 20:
            print(f"  ... 他 {len(result.orphan) - 20} 件")

    # ----- 出力 -----
    print()
    if not args.apply:
        print(f"dry-run のため {args.changed_out} は変更しません。")
        if result.orphan:
            print(f"          (孤児のレポートも未出力。--apply 指定時に "
                  f"{args.orphan_out} に書き出します)")
        print(f"本番実行する場合: py sync_files.py --apply")
        display.print_footer()
        return

    if not to_append:
        print("追記対象がありません。changed_files.txt は変更しません。")
    else:
        changed_out_path = Path(args.changed_out)
        existing = changed_list.read_paths(changed_out_path)
        merged = changed_list.merge_paths(existing, to_append)
        appended = len(merged) - len(existing)
        changed_list.write_paths(changed_out_path, merged)
        print(f"{args.changed_out} に {appended} 件追記しました "
              f"(既存 {len(existing)} 件 + 追記 {appended} 件 = 合計 {len(merged)} 件)")

    # 孤児は常にファイルへ書き出し (空でも空ファイルで上書き)
    orphan_path = Path(args.orphan_out)
    orphan_lines = [str(dst_root_path / e.relative) for e in result.orphan]
    orphan_path.write_text("\n".join(orphan_lines) + ("\n" if orphan_lines else ""),
                           encoding="utf-8")
    if orphan_lines:
        print(f"{args.orphan_out} に孤児 {len(orphan_lines)} 件を書き出しました "
              f"(削除はしません、手動で精査してください)")

    print()
    print("次のステップ:")
    if to_append:
        print("  1) py mirror_changed.py --dry-run --create-missing   # 確認")
        print("  2) py mirror_changed.py --create-missing             # 実コピー")
        print("  3) MusicBee でライブラリ再スキャン")
    else:
        print("  (差分なしのため Mirror 実行は不要)")
    display.print_footer()


if __name__ == "__main__":
    main()
