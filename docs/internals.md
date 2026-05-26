# 技術仕様 / トラブルシューティング

## iTunes Rating ↔ POPM マッピング (MP3)

MP3 の `POPM` フレームは 1byte (0〜255) で評価を持つが、「255をどう★に対応させるか」はプレイヤーごとに慣習が異なる。
本ツールは **MusicBee / Windows Media Player 標準** のマッピングを採用している。

| iTunes Rating | 星 | POPM 値 |
|---:|:---:|---:|
| 0 | (未評価) | (POPM フレーム自体を削除) |
| 20 | ★1 | 1 |
| 40 | ★2 | 64 |
| 60 | ★3 | 128 |
| 80 | ★4 | 196 |
| 100 | ★5 | 255 |

> **注意**: 単純な `rating * 2.55` だと ★1〜★4 の値が MusicBee 標準とズレる。必ずルックアップテーブル方式を使うこと。

## MP4 (M4A) のタグ仕様

```
Atom: ----:com.apple.iTunes:RATING
Type: フリーフォーム (FORMAT_TEXT)
Value: "0"〜"100" の文字列を UTF-8 でバイト化  (rating=0 ではアトム自体を削除)
```

- `\xa9rate` のような短いアトムは MP4 仕様に存在しない
- 業界標準は上記フリーフォームアトムで、MusicBee / foobar2000 / Mp3tag 等が読む

## ファイル本体の差分検出 (`sync_files.py`)

| 分類 | 条件 |
|---|---|
| `same` | 両方にあり、size 一致 & mtime 差が許容範囲内 |
| `updated` | 両方にあるが、size か mtime が違う |
| `new` | SRC にあり、DST に無い |
| `orphan` | DST にあり、SRC に無い (削除はせずレポートのみ) |

`shutil.copy2` は mtime を保存するため、コピー直後の DST.mtime == SRC.mtime となる。これにより、評価変更やタグ編集で SRC.mtime が動いた曲だけが `updated` として検出される設計。

## フィルタ条件（スキップ対象）

`sync_ratings.py` で以下のいずれかに該当するトラックは処理されない。

| 条件 | 理由 |
|---|---|
| `track.Kind != 1` | ローカルファイルでない (CD / Store / ストリーム) |
| `track.RatingKind != 0` | 自動推測の評価（ユーザー意思ではない） |
| `track.Location` が空 / ファイル不在 | 書き込めない |
| 拡張子が対応外 | サポート外形式 |
| `.m4p` | DRM 保護 |

> rating == 0 (未評価) でも、state に「以前は ★ が付いていた」記録があれば `removed` として処理される。

## iTunes COM API の主な利用箇所

| 呼び出し | 用途 |
|---|---|
| `win32com.client.Dispatch("iTunes.Application")` | iTunes に接続（未起動なら自動起動） |
| `itunes.LibraryPlaylist.Tracks` | 全トラック取得 |
| `track.Kind`, `track.Rating`, `track.RatingKind`, `track.Location` | 各種プロパティ |
| `itunes.ITObjectPersistentIDHigh(track)` / `Low(track)` | PersistentID（64bit）の取得 |

> **Note**: `track.PersistentID` というプロパティは存在しない。`Application` 経由で上位/下位32bit に分けて取得する必要がある (`pywin32` を使うときによくハマるポイント)。

## トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| `pywintypes.com_error` | iTunes が起動していない / アクセス権 | iTunes を起動してから再実行 |
| `PermissionError` | 他ソフトでファイル再生中、または同期中 | 再生停止、OneDrive 等の同期一時停止 |
| `FileNotFoundError` | iTunes が認識するパスとファイル実体がズレている | iTunes でファイル位置を更新 |
| MusicBee で星が反映されない | MusicBee のキャッシュ未更新 | MusicBee でライブラリ再スキャン |
| MusicBee 側だけ評価が古いまま | `changed_files.txt` がリセットされた状態で mirror を流してしまった等 | `py repair_mirror.py` で検出 → `--apply` で追記 → `py mirror_changed.py` で再反映 |
| `RatingKind` AttributeError | iTunes バージョンが古い | iTunes を最新版に更新 |
| `mirror_changed.py` で大量の `NO-DST` | SRC_ROOT / DST_ROOT のフォルダ構造がズレている | `--src-root` / `--dst-root` を正しいルートに指定、または `--create-missing` |
| `sync_state.json` の内容が古い気がする | 何らかの理由で state が現実と乖離 | `--force-all` で全件書き直し、または `del sync_state.json` |
| `python` が反応しない (Windows) | Microsoft Store スタブが優先されている | `py` コマンドを使用、または「アプリ実行エイリアス」で `python.exe` を無効化 |

## 安全に使うための推奨手順

このツールは音楽ファイルのタグを **直接書き換える**。万一の事故に備えて以下を推奨。

1. **必ず最初に `--dry-run`** で差分件数とサンプルを確認
2. **`--limit 5` などで少量テスト** を行い、MusicBee 等で表示を確認してから全件実行
3. 大切なファイルは別フォルダに **バックアップ** を取ってから実行
4. **OneDrive / Dropbox 等の同期フォルダ内** で実行する場合は、書き込み中のロック競合を避けるため同期を一時停止する

## 既知の制約

- **iTunes → ファイル の片方向同期のみ**: ファイル側のタグから iTunes へ書き戻す機能は無し
- **アルバム評価は同期しない**: トラック評価のみ
- **エラー時の自動リトライなし**: 失敗時は再実行 (state を見て差分のみ処理されるので無駄が少ない)
- **大規模ライブラリでも比較的高速**: 11,900 曲規模のライブラリで約 1 分（実行環境により変動）

## 関連リンク

- [iTunes COM Interface Documentation (非公式ミラー)](https://documentation.help/iTunesCOM/)
- [ID3v2.3 Specification - Popularimeter](https://id3.org/id3v2.3.0#Popularimeter)
- [mutagen Documentation](https://mutagen.readthedocs.io/)
