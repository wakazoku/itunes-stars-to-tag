# itunes-stars-to-tag

iTunes (Windows版) のライブラリに登録されている **星評価** を、音楽ファイルの **物理タグ** に書き込んで MusicBee 等の他プレイヤーで読めるようにする Python スクリプト。

## なぜ必要か

iTunes (Windows) の星評価は **iTunes ライブラリのデータベース内** に保存されており、ファイル本体には書き込まれません。  
そのため MusicBee や foobar2000 などの他プレイヤーから同じライブラリフォルダを参照しても、評価が引き継がれません。

このスクリプトは iTunes COM API 経由で評価を読み取り、各ファイルの形式に応じた **物理タグ** に評価を書き込むことで、他プレイヤーでも同じ評価を読めるようにします。

## 動作内容

- iTunes COM API 経由で全トラックを走査
- 「ユーザーが手で付けた星評価」だけを抽出（iTunes の自動推測評価は除外）
- 各ファイルの形式に応じて物理タグへ評価を書き込み
  - **MP3** → ID3v2.3 の `POPM` フレーム（MusicBee / Windows Media Player 互換マッピング）
  - **M4A (AAC / ALAC)** → `----:com.apple.iTunes:RATING` フリーフォームアトム

## 対応環境

| 項目 | 要件 |
|---|---|
| OS | Windows 10 / 11 |
| iTunes | Windows版 iTunes（Microsoft Store版 / Apple版どちらも可） |
| Python | 3.10 以上（3.11 で動作確認済み） |
| 対応ファイル形式 | MP3 / M4A (AAC) / M4A (ALAC) / MP4 / M4B |

### 対応外

- **FLAC / WAV / AIFF**: 未実装（必要なら拡張可能）
- **.m4p (DRM 保護)**: 書き込み不可かつ MusicBee で再生不可のため意図的にスキップ
- **iTunes Match / Apple Music クラウド楽曲**: ローカルファイルが無いためスキップ
- **半星 (★0.5刻み)**: 未対応（POPM マッピングを拡張すれば可）
- **macOS の Music.app**: COM が無いため非対応

## セットアップ

### 1. リポジトリ取得

```powershell
git clone https://github.com/<your-account>/star_rate_sync.git
cd star_rate_sync
```

### 2. 依存ライブラリのインストール

```powershell
pip install -r requirements.txt
```

`pywin32` / `mutagen` / `tqdm` がインストールされます。

### 3. インポート確認

```powershell
py -c "import win32com.client, mutagen, tqdm; print('OK')"
```

`OK` と表示されれば準備完了です。

> **Tips**: Windows 10/11 では `python` コマンドが Microsoft Store のスタブに当たって失敗することがあります。本ドキュメントでは Python ランチャー `py` を使う例で統一しています。

## 使い方

### 基本フロー

評価データを物理タグへ書き込む前に **必ずドライランで対象を確認** してください。

```powershell
# 1. iTunes を起動しておく
# 2. ドライラン (書き込みせず対象を表示)
py sync_ratings.py --dry-run

# 3. 少量テスト (5曲だけ書き込み、MusicBee 等で確認)
py sync_ratings.py --limit 5

# 4. (任意) 物理タグの読み戻し検証
py verify_tags.py

# 5. 全件実行 (--resume でテスト済み分はスキップ)
py sync_ratings.py --resume
```

### コマンドラインオプション

| オプション | 説明 |
|---|---|
| (なし) | 全件処理 (既処理分も上書き) |
| `--dry-run` | 書き込みせず対象だけ表示。本番前の確認用 |
| `--limit N` | 最大 N 曲で停止。少量テストや段階実行用 |
| `--resume` | `sync_progress.json` に記録された処理済みトラックをスキップ |

`--resume` と `--limit` を組み合わせて、段階的に実行することも可能です。

### 出力ファイル

実行すると以下のファイルがカレントディレクトリに生成されます（`.gitignore` で無視されます）。

| ファイル | 内容 |
|---|---|
| `sync_progress.json` | 処理済みトラックの PersistentID 一覧（再開用） |
| `sync_log.txt` | スキップ・失敗の詳細ログ |

## MusicBee 側の確認手順

書き込み後、MusicBee の表示を更新するために以下のいずれかを行ってください：

1. 該当曲を選択 → 右クリック → **「Send To」 → 「Library: Rescan」**
2. または `Ctrl+E` でタグを再読み込み
3. ライブラリ全体を再スキャンする場合: **Edit → Edit Preferences → Library → Scan now**

## 技術仕様

### iTunes Rating ↔ POPM マッピング (MP3)

MP3 の `POPM` フレームは 1byte (0〜255) で評価を持ちますが、「255をどう★に対応させるか」はプレイヤーごとに慣習が異なります。  
本ツールは **MusicBee / Windows Media Player 標準** のマッピングを採用しています。

| iTunes Rating | 星 | POPM 値 |
|---:|:---:|---:|
| 0 | (未評価) | 0 |
| 20 | ★1 | 1 |
| 40 | ★2 | 64 |
| 60 | ★3 | 128 |
| 80 | ★4 | 196 |
| 100 | ★5 | 255 |

> **注意**: 単純な `rating * 2.55` だと ★1〜★4 の値が MusicBee 標準とズレます。必ずルックアップテーブル方式を使用すること。

### MP4 (M4A) のタグ仕様

```
Atom: ----:com.apple.iTunes:RATING
Type: フリーフォーム (FORMAT_TEXT)
Value: "0"〜"100" の文字列を UTF-8 でバイト化
```

- `\xa9rate` のような短いアトムは MP4 仕様に存在しません
- 業界標準は上記フリーフォームアトムで、MusicBee / foobar2000 / Mp3tag 等が読みます

### フィルタ条件（スキップ対象）

以下のいずれかに該当するトラックは処理されません：

| 条件 | 理由 |
|---|---|
| `track.Kind != 1` | ローカルファイルでない (CD / Store / ストリーム) |
| `track.RatingKind != 0` | 自動推測の評価（ユーザー意思ではない） |
| `track.Rating == 0` | 未評価 |
| `track.Location` が空 / ファイル不在 | 書き込めない |
| 拡張子が対応外 | サポート外形式 |
| `.m4p` | DRM 保護 |

### iTunes COM API の主な利用箇所

| 呼び出し | 用途 |
|---|---|
| `win32com.client.Dispatch("iTunes.Application")` | iTunes に接続（未起動なら自動起動） |
| `itunes.LibraryPlaylist.Tracks` | 全トラック取得 |
| `track.Kind`, `track.Rating`, `track.RatingKind`, `track.Location` | 各種プロパティ |
| `itunes.ITObjectPersistentIDHigh(track)` / `Low(track)` | PersistentID（64bit）の取得 |

> **Note**: `track.PersistentID` というプロパティは存在しません。`Application` 経由で上位/下位32bit に分けて取得する必要があります（`pywin32` を使うときによくハマるポイント）。

## トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| `pywintypes.com_error` | iTunes が起動していない / アクセス権 | iTunes を起動してから再実行 |
| `PermissionError` | 他ソフトでファイル再生中、または同期中 | 再生停止、OneDrive 等の同期一時停止 |
| `FileNotFoundError` | iTunes が認識するパスとファイル実体がズレている | iTunes でファイル位置を更新 |
| MusicBee で星が反映されない | MusicBee のキャッシュ未更新 | MusicBee でライブラリ再スキャン |
| `RatingKind` AttributeError | iTunes バージョンが古い | iTunes を最新版に更新 |
| 大量に `failed` が出る | 依存ライブラリ未インストール / Python が古い | `pip install -r requirements.txt` を再実行、Python 3.10 以上を使用 |
| `python` が反応しない (Windows) | Microsoft Store スタブが優先されている | `py` コマンドを使用、または「アプリ実行エイリアス」で `python.exe` を無効化 |

## 安全に使うための推奨手順

このツールは音楽ファイルのタグを **直接書き換えます**。万一の事故に備えて以下を推奨します：

1. **必ず最初に `--dry-run`** で対象件数とサンプルを確認
2. **`--limit 5` などで少量テスト** を行い、MusicBee 等で表示を確認してから全件実行
3. 大切なファイルは別フォルダに **バックアップ** を取ってから実行
4. **OneDrive / Dropbox 等の同期フォルダ内** で実行する場合は、書き込み中のロック競合を避けるため同期を一時停止する

## 既知の制約

- **iTunes → ファイル の片方向同期のみ**: ファイル側のタグから iTunes へ書き戻す機能は無し
- **アルバム評価は同期しない**: トラック評価のみ
- **エラー時の自動リトライなし**: 失敗時は `--resume` で手動再実行
- **大規模ライブラリでも比較的高速**: 11,900 曲規模のライブラリで約 1 分（実行環境により変動）

## ライセンス

ライセンス未指定です。改変・再配布等を行う場合は事前にご相談ください。

## 関連

- [iTunes COM Interface Documentation (非公式ミラー)](https://documentation.help/iTunesCOM/)
- [ID3v2.3 Specification - Popularimeter](https://id3.org/id3v2.3.0#Popularimeter)
- [mutagen Documentation](https://mutagen.readthedocs.io/)
