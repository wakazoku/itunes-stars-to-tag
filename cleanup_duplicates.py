"""cleanup_duplicates.py

MusicBee 側 (DST) の内容完全一致重複ファイルを削除する。

既定は dry-run。``--apply`` 指定時のみファイルを削除する。
削除対象リストは ``find_duplicates.py`` が生成する
``reports/duplicate_delete_candidates.txt`` を想定。

Usage:
    py cleanup_duplicates.py --from-list reports/duplicate_delete_candidates.txt
    py cleanup_duplicates.py --from-list reports/duplicate_delete_candidates.txt --apply
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from starcore import display

DEFAULT_LIST = "reports/duplicate_delete_candidates.txt"
DEFAULT_LOG = "reports/deleted_duplicates.log"


def read_list(path: Path) -> list[Path]:
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[Path] = []
    for line in lines:
        line = line.strip()
        if line:
            out.append(Path(line))
    return out


def main() -> None:
    display.init_console_for_utf8()

    parser = argparse.ArgumentParser(
        description="重複ファイル削除リストに基づき DST 側の余剰コピーを削除する"
    )
    parser.add_argument(
        "--from-list",
        type=str,
        default=DEFAULT_LIST,
        help=f"削除対象の絶対パス一覧 (既定: {DEFAULT_LIST})",
    )
    parser.add_argument(
        "--log-out",
        type=str,
        default=DEFAULT_LOG,
        help=f"削除ログ出力先 (--apply 時のみ書き込み, 既定: {DEFAULT_LOG})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="実際にファイルを削除する (既定は dry-run)",
    )
    args = parser.parse_args()

    list_path = Path(args.from_list)
    if not list_path.is_file():
        print(f"[error] リストが見つかりません: {list_path}")
        sys.exit(2)

    targets = read_list(list_path)
    title = "重複ファイル削除"
    if not args.apply:
        title += "  (dry-run)"
    display.print_header(title)
    print(f"   リスト:  {list_path}")
    print(f"   対象件数: {len(targets):,} 件")
    print()

    missing: list[Path] = []
    present: list[Path] = []
    for p in targets:
        if p.is_file():
            present.append(p)
        else:
            missing.append(p)

    display.print_line(display.status_mark(len(missing), "warn"),
                       "存在しない:", len(missing), suffix="件")
    display.print_line(display.status_mark(len(present), "ok"),
                       "削除対象 (存在):", len(present), suffix="件")

    if missing:
        print()
        print("存在しないパス (先頭10件):")
        for p in missing[:10]:
            print(f"  - {p}")
        if len(missing) > 10:
            print(f"  ... 他 {len(missing) - 10} 件")

    if present:
        print()
        print("削除対象サンプル (先頭10件):")
        for p in present[:10]:
            print(f"  x {p}")
        if len(present) > 10:
            print(f"  ... 他 {len(present) - 10} 件")

    print()
    if not args.apply:
        print("dry-run のためファイルは削除しません。")
        print(f"本番実行: py cleanup_duplicates.py --from-list {list_path} --apply")
        display.print_footer()
        return

    if not present:
        print("削除対象がありません。")
        display.print_footer()
        return

    deleted: list[str] = []
    errors: list[str] = []
    for p in present:
        try:
            p.unlink()
            deleted.append(str(p))
        except OSError as exc:
            errors.append(f"{p}: {exc}")

    log_path = Path(args.log_out)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    log_lines = [f"# deleted at {ts}", f"# count: {len(deleted)}", ""]
    log_lines.extend(deleted)
    if errors:
        log_lines.extend(["", "# errors", *errors])
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    print(f"削除完了: {len(deleted):,} 件")
    if errors:
        print(f"エラー:   {len(errors):,} 件")
        for line in errors[:10]:
            print(f"  ! {line}")
    print(f"ログ: {log_path}")
    print()
    print("次のステップ:")
    print("  1) py sync_files.py --dry-run   # 孤児件数の確認")
    print("  2) MusicBee でライブラリ再スキャン")
    display.print_footer()


if __name__ == "__main__":
    main()
