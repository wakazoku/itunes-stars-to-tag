"""書き込み済みファイルのタグを読み戻して検証するツール。

sync_ratings.py で書き込んだ後に実行すると、``sync_state.json`` に記録された
``{rating, path}`` から物理タグを直接読み戻して、書き込んだ値が正しいかを検証する。

iTunes COM を介さないため iTunes 未起動でも動作する。

Usage:
    py verify_tags.py
    py verify_tags.py --limit 50

出力は verify_output.txt に UTF-8 で保存される。
"""
from __future__ import annotations

import argparse
from pathlib import Path

from mutagen.id3 import ID3, ID3NoHeaderError
from mutagen.mp4 import MP4

from starcore import display
from starcore import state as state_mod
from starcore.tagging import (
    ITUNES_TO_POPM,
    MP4_RATING_KEY,
    SUPPORTED_MP3,
    SUPPORTED_MP4,
)

STATE_FILE = "sync_state.json"
OUTPUT_FILE = "verify_output.txt"


def read_mp4_rating(path: Path) -> dict:
    audio = MP4(str(path))
    if MP4_RATING_KEY not in audio:
        return {"ok": False, "error": "RATING atom not found"}
    raw = audio[MP4_RATING_KEY][0]
    value = bytes(raw).decode("utf-8")
    return {"ok": True, "rating_str": value, "atom": MP4_RATING_KEY}


def read_mp3_rating(path: Path) -> dict:
    try:
        tags = ID3(str(path))
    except ID3NoHeaderError:
        return {"ok": False, "error": "ID3 header not found"}
    popms = tags.getall("POPM")
    if not popms:
        return {"ok": False, "error": "POPM frame not found"}
    p = popms[0]
    return {"ok": True, "email": p.email, "rating": p.rating, "count": p.count}


def main() -> None:
    display.init_console_for_utf8()
    parser = argparse.ArgumentParser(
        description="sync_state.json と物理タグの読み戻し検証"
    )
    parser.add_argument("--state", type=str, default=STATE_FILE,
                        help=f"検証する state ファイル (既定: {STATE_FILE})")
    parser.add_argument("--limit", type=int, default=0,
                        help="検証件数の上限 (0で全件)")
    parser.add_argument("--output", type=str, default=OUTPUT_FILE,
                        help=f"検証結果の出力先 (既定: {OUTPUT_FILE})")
    args = parser.parse_args()

    state_path = Path(args.state)
    if not state_path.exists():
        print(f"[error] {state_path} が見つかりません。先に sync_ratings.py を実行してください。")
        return

    state = state_mod.load(state_path)

    display.print_header("タグ読み戻し検証")
    print(f"   state エントリ:  {len(state):,} 件")
    if args.limit > 0:
        print(f"   検証件数上限:    {args.limit:,} 件")
    print()

    out_lines: list[str] = []
    out_lines.append(f"verified entries: target={len(state):,}")
    out_lines.append("=" * 80)

    stats = {"ok": 0, "mismatch": 0, "missing_file": 0, "missing_tag": 0,
             "unsupported": 0, "error": 0}

    items = list(state.items())
    if args.limit > 0:
        items = items[: args.limit]

    for idx, (pid, entry) in enumerate(items, 1):
        rating = entry.get("rating", 0)
        path_str = entry.get("path", "")
        path = Path(path_str)
        ext = path.suffix.lower()

        out_lines.append("")
        out_lines.append(
            f"[{idx}] {path.name}  ({ext})  state rating={rating} ({rating // 20} stars)"
        )

        if not path.exists():
            out_lines.append(f"    [NG] file not found at {path}")
            stats["missing_file"] += 1
            continue

        try:
            if ext in SUPPORTED_MP4:
                r = read_mp4_rating(path)
                if r.get("ok"):
                    expected = str(rating)
                    actual = r["rating_str"]
                    if actual == expected:
                        out_lines.append(f"    [OK] atom={r['atom']} value=\"{actual}\"")
                        stats["ok"] += 1
                    else:
                        out_lines.append(
                            f"    [MISMATCH] atom={r['atom']} expected=\"{expected}\" actual=\"{actual}\""
                        )
                        stats["mismatch"] += 1
                else:
                    out_lines.append(f"    [NG] {r['error']}")
                    stats["missing_tag"] += 1
            elif ext in SUPPORTED_MP3:
                r = read_mp3_rating(path)
                if r.get("ok"):
                    expected = ITUNES_TO_POPM.get(rating, 0)
                    actual = r["rating"]
                    if actual == expected:
                        out_lines.append(
                            f"    [OK] POPM rating={actual}, email={r['email']}, count={r['count']}"
                        )
                        stats["ok"] += 1
                    else:
                        out_lines.append(
                            f"    [MISMATCH] POPM expected={expected} actual={actual} email={r['email']}"
                        )
                        stats["mismatch"] += 1
                else:
                    out_lines.append(f"    [NG] {r['error']}")
                    stats["missing_tag"] += 1
            else:
                out_lines.append("    [SKIP] unsupported ext")
                stats["unsupported"] += 1
        except Exception as e:
            out_lines.append(f"    [ERR] {type(e).__name__}: {e}")
            stats["error"] += 1

    out_lines.append("")
    out_lines.append("=" * 80)
    out_lines.append(
        f"summary: ok={stats['ok']:,} / mismatch={stats['mismatch']:,} "
        f"/ missing_file={stats['missing_file']:,} / missing_tag={stats['missing_tag']:,} "
        f"/ unsupported={stats['unsupported']:,} / error={stats['error']:,}"
    )
    out_lines.append("")
    out_lines.append("MusicBee 互換 POPM ルックアップ参考:")
    for itu, popm in ITUNES_TO_POPM.items():
        out_lines.append(f"  iTunes {itu:>3} -> POPM {popm:>3} ({itu // 20} stars)")

    Path(args.output).write_text("\n".join(out_lines), encoding="utf-8")

    display.print_line(display.status_mark(stats["ok"], "result"),
                       "一致:", stats["ok"])
    display.print_line(display.status_mark(stats["mismatch"], "warn"),
                       "不一致:", stats["mismatch"])
    display.print_line(display.NEUTRAL_MARK, "タグ無し:", stats["missing_tag"])
    display.print_line(display.NEUTRAL_MARK, "ファイル無し:", stats["missing_file"])
    display.print_line(display.NEUTRAL_MARK, "サポート外形式:", stats["unsupported"])
    display.print_line(display.status_mark(stats["error"], "error"),
                       "エラー:", stats["error"])

    print()
    display.print_kv_section("出力ファイル", [
        (args.output, "(検証結果の詳細)"),
    ])
    display.print_footer()


if __name__ == "__main__":
    main()
