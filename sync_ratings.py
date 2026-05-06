"""
sync_ratings.py
iTunes (Windows) -> MP3 / M4A の物理タグへ星評価を書き込む。

Usage:
    py sync_ratings.py             # 通常実行
    py sync_ratings.py --dry-run   # 書き込みせず対象を表示
    py sync_ratings.py --resume    # 前回処理済みをスキップして再開
"""
import os
import json
import argparse
import logging
from pathlib import Path

import win32com.client
from mutagen.id3 import ID3, POPM, ID3NoHeaderError
from mutagen.mp4 import MP4, MP4FreeForm
from tqdm import tqdm

# MusicBee / Windows Media Player 互換マッピング
ITUNES_TO_POPM = {0: 0, 20: 1, 40: 64, 60: 128, 80: 196, 100: 255}

# iTunes COM API enum
ITTrackKindFile = 1
ITRatingKindUser = 0

LOG_FILE = "sync_log.txt"
PROGRESS_FILE = "sync_progress.json"


def write_mp3_rating(path: str, rating: int) -> None:
    """MP3にPOPMフレームで評価を書き込む。既存POPMは削除して上書き。"""
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    popm_value = ITUNES_TO_POPM.get(rating, 0)
    tags.delall("POPM")
    tags.add(POPM(email="no@email", rating=popm_value, count=0))
    tags.save(path, v2_version=3)


def write_mp4_rating(path: str, rating: int) -> None:
    """M4A/MP4にフリーフォームアトムで評価を書き込む。"""
    audio = MP4(path)
    audio["----:com.apple.iTunes:RATING"] = [
        MP4FreeForm(str(rating).encode("utf-8"), dataformat=MP4FreeForm.FORMAT_TEXT)
    ]
    audio.save()


def main() -> None:
    parser = argparse.ArgumentParser(description="iTunes -> 物理タグ同期")
    parser.add_argument("--dry-run", action="store_true",
                        help="書き込みはせず、対象だけ表示")
    parser.add_argument("--resume", action="store_true",
                        help="前回処理済みのトラックをスキップ")
    parser.add_argument("--limit", type=int, default=0,
                        help="指定件数で停止する (0で無制限、少量テストや段階実行用)")
    args = parser.parse_args()

    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        encoding="utf-8",
    )

    processed: set[str] = set()
    if args.resume and os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            processed = set(json.load(f))
        print(f"[resume] {len(processed):,} 曲をスキップします")

    print("iTunes に接続中... (起動していなければ自動起動します)")
    itunes = win32com.client.Dispatch("iTunes.Application")
    tracks = itunes.LibraryPlaylist.Tracks
    total = tracks.Count
    print(f"対象ライブラリ: {total:,} 曲")

    stats = {"synced": 0, "skipped": 0, "failed": 0}
    by_ext: dict[str, int] = {}  # 拡張子別の処理曲数 (synced or 予定)

    SUPPORTED_MP3 = {".mp3"}
    SUPPORTED_MP4 = {".m4a", ".mp4", ".m4b"}
    # .m4p は DRM 保護のため書き込み不可。MusicBee でも再生できないので除外
    DRM_PROTECTED = {".m4p"}

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
                if rating == 0:
                    stats["skipped"] += 1
                    continue

                # iTunes COM APIではPersistentIDはApplication経由で64bitを上位/下位に分けて取得する
                pid_high = itunes.ITObjectPersistentIDHigh(track)
                pid_low = itunes.ITObjectPersistentIDLow(track)
                pid = f"{pid_high}_{pid_low}"
                if pid in processed:
                    continue

                path = track.Location
                if not path or not os.path.exists(path):
                    logging.warning(f"path-missing: {track.Name} :: {path}")
                    stats["skipped"] += 1
                    continue

                ext = Path(path).suffix.lower()

                if args.dry_run:
                    tqdm.write(f"[dry-run] {rating // 20}star {ext} {track.Name}")
                else:
                    if ext in SUPPORTED_MP3:
                        write_mp3_rating(path, rating)
                    else:
                        write_mp4_rating(path, rating)
                    if args.limit > 0:  # Step 7 テスト時は処理パスを表示
                        tqdm.write(f"  WROTE {rating // 20}star -> {path}")

                processed.add(pid)
                stats["synced"] += 1
                by_ext[ext] = by_ext.get(ext, 0) + 1

                if args.limit > 0 and stats["synced"] >= args.limit:
                    tqdm.write(f"\n[limit] {args.limit} 曲到達のため停止します")
                    break

            except Exception as e:
                stats["failed"] += 1
                logging.error(f"failed[{i}]: {e}")

    finally:
        if not args.dry_run:
            with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                json.dump(list(processed), f)

    label = "対象" if args.dry_run else "synced"
    print(
        f"\n完了: {label}={stats['synced']:,} / "
        f"skipped={stats['skipped']:,} / failed={stats['failed']:,}"
    )
    if by_ext:
        print("内訳:")
        for ext, n in sorted(by_ext.items(), key=lambda x: -x[1]):
            print(f"  {ext}: {n:,} 曲")
    print(f"詳細ログ: {LOG_FILE}")


if __name__ == "__main__":
    main()
