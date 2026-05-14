"""mirror_changed.py

``changed_files.txt`` に並んでいる絶対パスを SRC_ROOT → DST_ROOT で
対応付け直し、コピー先に既に同名ファイルが存在する場合に上書きする。

iTunes 原本側 (タグ書き込み済み) と MusicBee 側コピーを同期するために使用する。

SRC_ROOT / DST_ROOT の指定は以下の優先順位で解決される:
    1. CLI 引数 (--src-root / --dst-root)
    2. 環境変数 STAR_RATE_SYNC_SRC_ROOT / STAR_RATE_SYNC_DST_ROOT
       (.env ファイルから自動で読み込まれる)
    3. どちらも未指定の場合はエラー

Usage:
    py mirror_changed.py
    py mirror_changed.py --dry-run
    py mirror_changed.py --dst-root "D:\\Music\\MusicBee\\Music"
    py mirror_changed.py --create-missing
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

from starcore import display
from starcore.paths import to_mirror

LIST_FILE = "changed_files.txt"
LOG_FILE = "mirror_log.txt"

ENV_SRC_ROOT = "STAR_RATE_SYNC_SRC_ROOT"
ENV_DST_ROOT = "STAR_RATE_SYNC_DST_ROOT"


def main() -> None:
    display.init_console_for_utf8()
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="変更ファイルを SRC_ROOT -> DST_ROOT へミラーコピー"
    )
    parser.add_argument("--src-root", type=str, default=None,
                        help=f"iTunes 側の音楽フォルダのルート (未指定なら環境変数 {ENV_SRC_ROOT})")
    parser.add_argument("--dst-root", type=str, default=None,
                        help=f"MusicBee 側の音楽フォルダのルート (未指定なら環境変数 {ENV_DST_ROOT})")
    parser.add_argument("--list", type=str, default=LIST_FILE,
                        help=f"コピー対象ファイル一覧 (既定: {LIST_FILE})")
    parser.add_argument("--dry-run", action="store_true",
                        help="コピーせず予定だけ表示")
    parser.add_argument("--create-missing", action="store_true",
                        help="コピー先が存在しないときも親フォルダごと作って新規コピーする")
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

    list_path = Path(args.list)
    if not list_path.exists():
        print(f"[error] {list_path} が見つかりません。先に sync_ratings.py を実行してください。")
        sys.exit(1)

    src_lines = [
        line.strip()
        for line in list_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    title = "変更ファイル ミラーコピー"
    if args.dry_run:
        title += "  (dry-run)"
    display.print_header(title)
    print(f"   対象:    {len(src_lines):,} 件")
    print(f"   SRC:     {src_root}")
    print(f"   DST:     {dst_root}")
    if args.create_missing:
        print("   mode:    --create-missing (親フォルダごと作成して新規コピー)")
    print()

    stats = {
        "copied": 0,
        "created": 0,
        "skipped_no_dst": 0,
        "skipped_no_src": 0,
        "skipped_out_of_root": 0,
        "failed": 0,
    }
    log_lines: list[str] = []
    # 未処理 (NO-DST / NO-SRC / OUT-OF-SRC-ROOT / FAIL) の行はここに残し、
    # 後で changed_files.txt を「未処理ぶんだけに」書き戻す。
    # こうすると次回 mirror は未処理ぶんだけが対象になる。
    remaining_lines: list[str] = []

    for src_str in src_lines:
        src = Path(src_str)
        if not src.exists():
            stats["skipped_no_src"] += 1
            log_lines.append(f"NO-SRC               {src}")
            remaining_lines.append(src_str)
            continue

        dst = to_mirror(src, src_root, dst_root)
        if dst is None:
            stats["skipped_out_of_root"] += 1
            log_lines.append(f"OUT-OF-SRC-ROOT      {src}")
            remaining_lines.append(src_str)
            continue

        if not dst.exists():
            if args.create_missing:
                if args.dry_run:
                    print(f"[dry-run] CREATE {dst}")
                    stats["created"] += 1
                    continue
                try:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    stats["created"] += 1
                except Exception as e:
                    stats["failed"] += 1
                    log_lines.append(f"FAIL                 {src} -> {dst} :: {e}")
                    remaining_lines.append(src_str)
            else:
                stats["skipped_no_dst"] += 1
                log_lines.append(f"NO-DST               {dst}")
                remaining_lines.append(src_str)
            continue

        if args.dry_run:
            print(f"[dry-run] COPY  {dst}")
            stats["copied"] += 1
            continue
        try:
            shutil.copy2(src, dst)
            stats["copied"] += 1
        except Exception as e:
            stats["failed"] += 1
            log_lines.append(f"FAIL                 {src} -> {dst} :: {e}")
            remaining_lines.append(src_str)

    success_total = stats["copied"] + stats["created"]
    skipped_total = (
        stats["skipped_no_dst"]
        + stats["skipped_no_src"]
        + stats["skipped_out_of_root"]
    )

    if args.dry_run:
        success_label = "コピー予定:"
        copied_label = "上書き予定:"
        created_label = "新規作成予定:"
    else:
        success_label = "コピー成功:"
        copied_label = "上書きコピー:"
        created_label = "新規作成:"

    print()
    display.print_line(display.status_mark(success_total, "result"),
                       success_label, success_total, suffix="件")
    display.print_tree_line(copied_label, stats["copied"], suffix="件")
    display.print_tree_line(created_label, stats["created"], suffix="件", last=True)
    display.print_line(display.NEUTRAL_MARK, "スキップ:", skipped_total, suffix="件")
    display.print_tree_line("コピー先に無し:", stats["skipped_no_dst"], suffix="件")
    display.print_tree_line("コピー元に無し:", stats["skipped_no_src"], suffix="件")
    display.print_tree_line("SRC_ROOT 外:", stats["skipped_out_of_root"], suffix="件", last=True)
    display.print_line(display.status_mark(stats["failed"], "error"),
                       "失敗:", stats["failed"], suffix="件")

    print()
    if log_lines:
        Path(LOG_FILE).write_text("\n".join(log_lines), encoding="utf-8")
        display.print_kv_section("出力ファイル", [
            (LOG_FILE, f"(詳細ログ、{len(log_lines):,} 行)"),
        ])
    else:
        print("詳細ログ: なし (全件処理されました)")

    # 本番実行時のみ、未処理ぶんだけを残して changed_files.txt を書き換える。
    # dry-run では一覧の状態を一切変えない (再現性を保つため)。
    if not args.dry_run and src_lines:
        new_content = "\n".join(remaining_lines)
        if remaining_lines:
            new_content += "\n"
        list_path.write_text(new_content, encoding="utf-8")
        cleared = len(src_lines) - len(remaining_lines)
        if remaining_lines and cleared > 0:
            print(f"{args.list}: 処理済み {cleared} 件を除外、未処理 {len(remaining_lines)} 件を残しました")
        elif remaining_lines:
            print(f"{args.list}: 未処理 {len(remaining_lines)} 件 (今回処理できたものはありません)")
        else:
            print(f"{args.list}: クリアしました (全件ミラー済み)")

    display.print_footer()


if __name__ == "__main__":
    main()
