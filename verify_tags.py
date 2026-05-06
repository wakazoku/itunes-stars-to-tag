"""書き込み済みファイルのタグを読み戻して検証するツール。

sync_ratings.py で書き込んだ後に実行すると、sync_progress.json に記録された
PersistentID から iTunes 経由でファイルパスを再取得し、mutagen で物理タグを
読み戻して、書き込んだ値が正しいかを検証する。

Usage:
    py verify_tags.py

出力は verify_output.txt に UTF-8 で保存される。
"""
import json
from pathlib import Path

import win32com.client
from mutagen.id3 import ID3
from mutagen.mp4 import MP4

ITUNES_TO_POPM = {0: 0, 20: 1, 40: 64, 60: 128, 80: 196, 100: 255}


def verify_mp4(path: Path) -> dict:
    audio = MP4(str(path))
    key = "----:com.apple.iTunes:RATING"
    if key not in audio:
        return {"ok": False, "error": "RATING atom not found"}
    raw = audio[key][0]
    value = bytes(raw).decode("utf-8")
    return {"ok": True, "rating_str": value, "atom": key}


def verify_mp3(path: Path) -> dict:
    tags = ID3(str(path))
    popms = tags.getall("POPM")
    if not popms:
        return {"ok": False, "error": "POPM frame not found"}
    p = popms[0]
    return {"ok": True, "email": p.email, "rating": p.rating, "count": p.count}


def main() -> None:
    progress_file = Path("sync_progress.json")
    if not progress_file.exists():
        print("sync_progress.json not found")
        return

    pids = set(json.loads(progress_file.read_text(encoding="utf-8")))
    print(f"processed pids: {len(pids)}")

    itunes = win32com.client.Dispatch("iTunes.Application")
    tracks = itunes.LibraryPlaylist.Tracks
    total = tracks.Count

    print("scanning library to find processed tracks...")
    found: list[dict] = []
    for i in range(1, total + 1):
        if len(found) >= len(pids):
            break
        try:
            track = tracks.Item(i)
            if track.Kind != 1:
                continue
            pid_high = itunes.ITObjectPersistentIDHigh(track)
            pid_low = itunes.ITObjectPersistentIDLow(track)
            pid = f"{pid_high}_{pid_low}"
            if pid in pids:
                found.append({
                    "name": track.Name,
                    "rating": track.Rating,
                    "path": track.Location,
                })
        except Exception:
            continue

    out_lines: list[str] = []
    out_lines.append(f"verified files: {len(found)} / {len(pids)}")
    out_lines.append("=" * 80)

    for idx, t in enumerate(found, 1):
        p = Path(t["path"])
        ext = p.suffix.lower()
        itu_rating = t["rating"]
        out_lines.append("")
        out_lines.append(f"[{idx}] {p.name}  ({ext})  iTunes rating={itu_rating} ({itu_rating // 20} stars)")
        if not p.exists():
            out_lines.append(f"    [NG] file not found at {p}")
            continue
        try:
            if ext in {".m4a", ".mp4", ".m4b"}:
                r = verify_mp4(p)
                if r.get("ok"):
                    expected = str(itu_rating)
                    actual = r["rating_str"]
                    status = "OK" if actual == expected else f"MISMATCH (expected={expected})"
                    out_lines.append(f"    [{status}] atom={r['atom']} value=\"{actual}\"")
                else:
                    out_lines.append(f"    [NG] {r['error']}")
            elif ext == ".mp3":
                r = verify_mp3(p)
                if r.get("ok"):
                    expected = ITUNES_TO_POPM.get(itu_rating, 0)
                    actual = r["rating"]
                    status = "OK" if actual == expected else f"MISMATCH (expected={expected})"
                    out_lines.append(f"    [{status}] POPM rating={actual}, email={r['email']}, count={r['count']}")
                else:
                    out_lines.append(f"    [NG] {r['error']}")
            else:
                out_lines.append(f"    [SKIP] unsupported ext")
        except Exception as e:
            out_lines.append(f"    [ERR] {type(e).__name__}: {e}")

    out_lines.append("")
    out_lines.append("=" * 80)
    out_lines.append("MusicBee 互換 POPM ルックアップ参考:")
    for itu, popm in ITUNES_TO_POPM.items():
        out_lines.append(f"  iTunes {itu:>3} -> POPM {popm:>3} ({itu // 20} stars)")

    Path("verify_output.txt").write_text("\n".join(out_lines), encoding="utf-8")
    print("wrote verify_output.txt")


if __name__ == "__main__":
    main()
