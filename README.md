# star_rate_sync

iTunes (Windows版) のライブラリに登録されている **星評価** を、音楽ファイルの **物理タグ** に書き込んで MusicBee 等の他プレイヤーで読めるようにする Python スクリプト。

加えて、変更があったファイルだけを別フォルダ (例: MusicBee 用のコピー先) へミラーコピーする機能を持つ。

## なぜ必要か

iTunes (Windows) の星評価は **iTunes ライブラリのデータベース内** に保存されており、ファイル本体には書き込まれません。
そのため MusicBee や foobar2000 などの他プレイヤーから同じライブラリフォルダを参照しても、評価が引き継がれません。

このスクリプトは iTunes COM API 経由で評価を読み取り、各ファイルの形式に応じた **物理タグ** に評価を書き込むことで、他プレイヤーでも同じ評価を読めるようにします。

iTunes 用フォルダとは別のフォルダ (コピー) を MusicBee に見せている場合は、`mirror_changed.py` を使って **変更があったファイルだけ** をコピー先に上書きできます。

## 動作内容

- iTunes COM API 経由で全トラックを走査
- 「ユーザーが手で付けた星評価」だけを抽出（iTunes の自動推測評価は除外）
- 各ファイルの形式に応じて物理タグへ評価を書き込み
  - **MP3** → ID3v2.3 の `POPM` フレーム（MusicBee / Windows Media Player 互換マッピング）
  - **M4A (AAC / ALAC)** → `----:com.apple.iTunes:RATING` フリーフォームアトム
- **前回値との差分 (new / modified / removed) だけを書き込み**、変更があった曲を `changed_files.txt` に出力
- `mirror_changed.py` で `changed_files.txt` の各曲を SRC_ROOT → DST_ROOT で対応付け直してコピー

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

`pywin32` / `mutagen` / `tqdm` / `python-dotenv` がインストールされます。

開発 (テスト実行) もする場合:

```powershell
pip install -r requirements-dev.txt
```

`pytest` が追加されます。

### 3. インポート確認

```powershell
py -c "import win32com.client, mutagen, tqdm, dotenv; print('OK')"
```

`OK` と表示されれば準備完了です。

### 4. `.env` の作成 (mirror_changed.py を使う場合のみ)

`mirror_changed.py` を使うときは、SRC/DST フォルダのパスを `.env` で指定します。`.env.example` をコピーして編集してください。

```powershell
copy .env.example .env
notepad .env
```

`.env` の中身:

```
STAR_RATE_SYNC_SRC_ROOT=C:\Users\YOUR_NAME\Music\iTunes\iTunes Media\Music
STAR_RATE_SYNC_DST_ROOT=C:\Users\YOUR_NAME\Music\MusicBee\Music
```

`.env` は `.gitignore` で除外されるので、リポジトリにコミットされません。CLI 引数 `--src-root` / `--dst-root` を渡せばそちらが優先されます。

> **Tips**: Windows 10/11 では `python` コマンドが Microsoft Store のスタブに当たって失敗することがあります。本ドキュメントでは Python ランチャー `py` を使う例で統一しています。

## 使い方

### 基本フロー (iTunes 原本だけ更新する)

評価データを物理タグへ書き込む前に **必ずドライランで対象を確認** してください。

```powershell
# 1. iTunes を起動しておく
# 2. ドライラン (書き込みせず差分を表示)
py sync_ratings.py --dry-run

# 3. 少量テスト (5件だけ書き込み、MusicBee 等で確認)
py sync_ratings.py --limit 5

# 4. (任意) 物理タグの読み戻し検証
py verify_tags.py

# 5. 差分のみ書き込み (二回目以降は自動的にスキップされる)
py sync_ratings.py
```

### MusicBee 用に別フォルダへ反映する場合

iTunes 原本フォルダ (`C:\...\iTunes Media\Music`) とは別に、コピーした MusicBee 用フォルダ (`C:\...\MusicBee\Music`) を MusicBee に見せている場合の手順:

```powershell
# 1. iTunes 原本のタグを更新し、変更分を changed_files.txt に出力
py sync_ratings.py

# 2. 変更があったファイルだけを MusicBee 側のフォルダへコピー
py mirror_changed.py --dry-run     # 予定だけ表示
py mirror_changed.py               # 実コピー
```

`mirror_changed.py` は SRC_ROOT / DST_ROOT の **相対パス構造が同じであること** を前提に、`src/Artist/Album/song.mp3` を `dst/Artist/Album/song.mp3` へ上書きコピーします。

### `sync_ratings.py` のコマンドラインオプション

| オプション | 説明 |
|---|---|
| (なし) | `sync_state.json` を見て **差分 (new / modified / removed) だけ** 書き込み |
| `--dry-run` | 書き込みせず差分対象だけ表示。本番前の確認用 |
| `--limit N` | 差分が N 件に達した時点で停止。少量テスト用 |
| `--force-all` | state を無視して全評価曲を書き直す。state も上書きされる |
| `--changed-out PATH` | 変更ファイル一覧の出力先 (既定: `changed_files.txt`) |
| `--detail` | rating 遷移マップ (`★n → ★m が何曲`) も表示する |

`--resume` は廃止されました。`sync_state.json` による差分検出が常時 ON のため、同じ役目がデフォルト動作に吸収されています。

### `mirror_changed.py` のコマンドラインオプション

| オプション | 既定値 | 説明 |
|---|---|---|
| `--src-root PATH` | `.env` の `STAR_RATE_SYNC_SRC_ROOT` | iTunes 側 (コピー元) の音楽フォルダのルート |
| `--dst-root PATH` | `.env` の `STAR_RATE_SYNC_DST_ROOT` | MusicBee 側 (コピー先) の音楽フォルダのルート |
| `--list PATH` | `changed_files.txt` | コピー対象ファイル一覧 |
| `--dry-run` | off | コピーせず予定だけ表示 |
| `--create-missing` | off | コピー先に同名ファイルが無くても、親フォルダごと作って新規コピーする |

パスの解決順:

1. CLI 引数 (`--src-root` / `--dst-root`) が最優先
2. `.env` の `STAR_RATE_SYNC_SRC_ROOT` / `STAR_RATE_SYNC_DST_ROOT`
3. それも未指定ならエラー (exit code 2)

> **デフォルト動作**: コピー先にファイルが無い場合は **スキップしてログに残す** (=「フォルダ構造のズレ」を検出しやすい)。事前に MusicBee 側にコピーしていない状態で大量に新規作成して欲しい場合のみ `--create-missing` を指定してください。

### `verify_tags.py` のコマンドラインオプション

書き込み済みファイルのタグを読み戻して、`sync_state.json` の値と一致するかを検証します。iTunes COM は使いません (iTunes 未起動でも実行可)。

| オプション | 既定値 | 説明 |
|---|---|---|
| `--state PATH` | `sync_state.json` | 検証対象の state ファイル |
| `--limit N` | `0` (全件) | 検証件数の上限 |
| `--output PATH` | `verify_output.txt` | 検証結果の出力先 |

### 出力ファイル

実行すると以下のファイルがカレントディレクトリに生成されます（`.gitignore` で無視されます）。

| ファイル | 出力元 | 内容 |
|---|---|---|
| `sync_state.json` | `sync_ratings.py` | PID → `{ rating, path }`。差分判定のための「前回値」 |
| `sync_state.json.broken` | `sync_ratings.py` | JSON が破損していた場合の自動退避先 |
| `changed_files.txt` | `sync_ratings.py` | 今回 new / modified / removed 判定された曲の絶対パス一覧 |
| `sync_log.txt` | `sync_ratings.py` | スキップ・失敗の詳細ログ |
| `mirror_log.txt` | `mirror_changed.py` | コピー失敗・コピー先不在の詳細ログ |
| `verify_output.txt` | `verify_tags.py` | タグ読み戻し検証結果 |

> 旧 `sync_progress.json` (PID リスト) は新仕様では使われません。残っていても無視されるので、不要なら削除して構いません。

## MusicBee 側の確認手順

書き込み後 (および `mirror_changed.py` でコピー後)、MusicBee の表示を更新するために以下のいずれかを行ってください：

1. 該当曲を選択 → 右クリック → **「Send To」 → 「Library: Rescan」**
2. または `Ctrl+E` でタグを再読み込み
3. ライブラリ全体を再スキャンする場合: **Edit → Edit Preferences → Library → Scan now**

## 差分検出の仕組み

`sync_ratings.py` は実行のたびに、各曲について次の 4 通りに分類します。

| 分類 | 条件 | 動作 |
|---|---|---|
| `new` | 前回 state に無し（または `rating == 0`）で、iTunes 側が 1 以上 | タグへ書き込み、`changed_files.txt` に追加 |
| `modified` | 前回値と異なる（双方 1 以上） | タグへ上書き、`changed_files.txt` に追加 |
| `removed` | 前回 1 以上、iTunes 側で 0 (=星を外した) | タグを削除し state からも削除、`changed_files.txt` に追加 |
| `none` | 変化なし | 何もしない |

これにより、二回目以降の実行は **iTunes 側で変わった曲だけ** 触ります。MusicBee 側へのコピー量も最小限になります。

### 「state が信用できない」ときの逃げ道

| 手段 | 方法 | 効果 |
|---|---|---|
| 全件強制再書き込み | `py sync_ratings.py --force-all` | state を無視して全評価曲を書き直し、state を上書きする |
| state リセット | `del sync_state.json` してから普通に実行 | 全評価曲が `new` 扱い |
| 特定曲だけ復旧 | `sync_state.json` を開いて該当 PID 行を削除 | 次回その曲だけ `new` 扱い |

加えて、`sync_state.json` が JSON として壊れていた場合は **自動で `.broken` にリネームされ、空 state で続行** されます。詰むことはありません。

## テスト

純粋ロジック (`starcore/diff.py` `paths.py` `state.py`) は pytest で単体テスト済みです。

```powershell
pip install -r requirements-dev.txt
py -m pytest
```

主な観点:

- `diff.classify`: new / modified / removed / none の網羅
- `paths.to_mirror`: 大文字小文字の差・末尾セパレータ・SRC 外パスなどの分岐
- `state.load`/`save`: JSON round-trip、Unicode 維持、壊れた JSON の自動退避

iTunes COM 部分と音声ファイルへの実 I/O はテスト対象外です (実環境依存のため、必要に応じて `--dry-run` で確認してください)。

## ディレクトリ構成

```
star_rate_sync/
├── sync_ratings.py        # iTunes -> ファイルタグ同期 (CLI)
├── mirror_changed.py      # 変更ファイルを別フォルダへミラーコピー (CLI)
├── verify_tags.py         # 書き込み済みタグの読み戻し検証 (CLI)
├── starcore/              # 純粋ロジック (テスト容易な内部パッケージ)
│   ├── diff.py            # 差分判定
│   ├── paths.py           # src -> dst のパス変換
│   ├── state.py           # sync_state.json の load/save
│   └── tagging.py         # MP3 / M4A への rating 書き込み
├── tests/                 # pytest テスト
├── conftest.py            # pytest rootdir 設定
├── .env.example           # mirror_changed.py 用の設定見本
├── .env                   # ローカル設定 (gitignore 対象)
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

## 技術仕様

### iTunes Rating ↔ POPM マッピング (MP3)

MP3 の `POPM` フレームは 1byte (0〜255) で評価を持ちますが、「255をどう★に対応させるか」はプレイヤーごとに慣習が異なります。
本ツールは **MusicBee / Windows Media Player 標準** のマッピングを採用しています。

| iTunes Rating | 星 | POPM 値 |
|---:|:---:|---:|
| 0 | (未評価) | (POPM フレーム自体を削除) |
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
Value: "0"〜"100" の文字列を UTF-8 でバイト化  (rating=0 ではアトム自体を削除)
```

- `\xa9rate` のような短いアトムは MP4 仕様に存在しません
- 業界標準は上記フリーフォームアトムで、MusicBee / foobar2000 / Mp3tag 等が読みます

### フィルタ条件（スキップ対象）

以下のいずれかに該当するトラックは処理されません：

| 条件 | 理由 |
|---|---|
| `track.Kind != 1` | ローカルファイルでない (CD / Store / ストリーム) |
| `track.RatingKind != 0` | 自動推測の評価（ユーザー意思ではない） |
| `track.Location` が空 / ファイル不在 | 書き込めない |
| 拡張子が対応外 | サポート外形式 |
| `.m4p` | DRM 保護 |

> rating == 0 (未評価) でも、state に「以前は ★ が付いていた」記録があれば `removed` として処理されます。

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
| `mirror_changed.py` で大量の `NO-DST` | SRC_ROOT / DST_ROOT のフォルダ構造がズレている | `--src-root` / `--dst-root` を正しいルートに指定、または `--create-missing` |
| `sync_state.json` の内容が古い気がする | 何らかの理由で state が現実と乖離 | `--force-all` で全件書き直し、または `del sync_state.json` |
| `python` が反応しない (Windows) | Microsoft Store スタブが優先されている | `py` コマンドを使用、または「アプリ実行エイリアス」で `python.exe` を無効化 |

## 安全に使うための推奨手順

このツールは音楽ファイルのタグを **直接書き換えます**。万一の事故に備えて以下を推奨します：

1. **必ず最初に `--dry-run`** で差分件数とサンプルを確認
2. **`--limit 5` などで少量テスト** を行い、MusicBee 等で表示を確認してから全件実行
3. 大切なファイルは別フォルダに **バックアップ** を取ってから実行
4. **OneDrive / Dropbox 等の同期フォルダ内** で実行する場合は、書き込み中のロック競合を避けるため同期を一時停止する

## 既知の制約

- **iTunes → ファイル の片方向同期のみ**: ファイル側のタグから iTunes へ書き戻す機能は無し
- **アルバム評価は同期しない**: トラック評価のみ
- **エラー時の自動リトライなし**: 失敗時は再実行 (state を見て差分のみ処理されるので無駄が少ない)
- **大規模ライブラリでも比較的高速**: 11,900 曲規模のライブラリで約 1 分（実行環境により変動）

## ライセンス

ライセンス未指定です。改変・再配布等を行う場合は事前にご相談ください。

## 関連

- [iTunes COM Interface Documentation (非公式ミラー)](https://documentation.help/iTunesCOM/)
- [ID3v2.3 Specification - Popularimeter](https://id3.org/id3v2.3.0#Popularimeter)
- [mutagen Documentation](https://mutagen.readthedocs.io/)
