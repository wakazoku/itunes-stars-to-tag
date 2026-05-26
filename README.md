# itunes-stars-to-tag

iTunes (Windows版) のライブラリに登録されている **星評価** を、音楽ファイルの **物理タグ** に書き込んで MusicBee 等の他プレイヤーで読めるようにする Python ツール群。

加えて、変更があったファイルだけを別フォルダ (例: MusicBee 用のコピー先) へミラーコピーする機能と、評価とは独立に **ファイル本体の差分同期** (mtime+size 比較) を行う機能を持つ。

## なぜ必要か

iTunes (Windows) の星評価は **iTunes ライブラリのデータベース内** に保存され、ファイル本体には書き込まれない。
そのため MusicBee や foobar2000 等の他プレイヤーから同じライブラリフォルダを参照しても、評価が引き継がれない。

このツールは iTunes COM API 経由で評価を読み取り、各ファイルの形式に応じた **物理タグ** に書き込む。iTunes と別フォルダを MusicBee に見せている場合は、変更があったファイルだけをミラーコピーできる。

## 対応環境

| 項目 | 要件 |
|---|---|
| OS | Windows 10 / 11 |
| iTunes | Windows版 iTunes（Microsoft Store版 / Apple版どちらも可） |
| Python | 3.10 以上（3.11 で動作確認済み） |
| 対応ファイル形式 | MP3 / M4A (AAC) / M4A (ALAC) / MP4 / M4B |

**対応外**: FLAC / WAV / AIFF / .m4p (DRM) / iTunes Match / 半星評価 / macOS

## セットアップ

```powershell
git clone https://github.com/<your-account>/star_rate_sync.git
cd star_rate_sync
pip install -r requirements.txt

# .env でフォルダのパスを設定 (mirror 系を使うとき)
copy .env.example .env
notepad .env
```

`.env` の中身:

```
STAR_RATE_SYNC_SRC_ROOT=C:\Users\YOUR_NAME\Music\iTunes\iTunes Media\Music
STAR_RATE_SYNC_DST_ROOT=C:\Users\YOUR_NAME\Music\MusicBee\Music
```

> **Tips**: Windows 10/11 では `python` コマンドが Microsoft Store のスタブに当たって失敗することがある。本ドキュメントでは Python ランチャー `py` を使う例で統一している。

## 使い方

### GUI ランチャー (推奨)

`start_gui.pyw` をダブルクリックすると Tkinter のウィンドウが立ち上がる。タブは 2 階層:

- **評価同期**: Sync / Mirror / Verify / Repair
- **ファイル同期**: Files

書き込み系タブは初期状態で **dry-run が ON**。一度確認してからチェックを外して本番実行する。

詳細は [docs/gui.md](docs/gui.md)。

#### GUI シナリオ集

下記の CLI シナリオ集 (A〜E) を GUI でやる場合の操作手順。
各ステップで「dry-run を一度実行 → 出力確認 → 本番実行」を挟むのが安全。

##### A. 普段の運用 (評価 + ファイル本体を両方同期)

1. iTunes を起動しておく
2. `[評価同期] > Sync` タブ → dry-run のまま「▶ 実行」→ 件数確認 → dry-run チェックを外して再実行
3. `[ファイル同期] > Files` タブ → 「▶ 実行」(dry-run) → 件数確認 → `apply` ON で再実行
4. `[評価同期] > Mirror` タブ → `create-missing` ON、dry-run のまま「▶ 実行」→ dry-run チェックを外して再実行
5. MusicBee でライブラリ再スキャン

##### B. 評価だけ変えたとき

1. `[評価同期] > Sync` → dry-run 確認 → 本番実行
2. `[評価同期] > Mirror` → dry-run 確認 → 本番実行 (`create-missing` は OFF のままで OK)

##### C. iTunes に新曲を追加しただけ (評価変更なし)

1. `[ファイル同期] > Files` → dry-run 確認 → `apply` ON で実行
2. `[評価同期] > Mirror` → `create-missing` ON で実行

##### D. MusicBee 側が古い気がする (救出)

1. `[評価同期] > Repair` → dry-run のまま「▶ 実行」→ ズレ件数を確認
2. 同タブで `apply` ON + `include-missing` ON にして再実行
3. `[評価同期] > Mirror` → `create-missing` ON で実行

##### E. 孤児 (DST にだけある曲) の精査

`[ファイル同期] > Files` を `apply` ON で実行すると、リポジトリ直下に `orphan_files.txt` が生成される。
中身を眺めて、不要ならエクスプローラで手動削除。自動削除はしない設計。

### CLI シナリオ集

#### A. 普段の運用 (評価 + ファイル本体を両方同期)

評価変更、新曲追加、タグ編集、を一気に MusicBee へ反映。

```powershell
# 1. iTunes を起動しておく

# 2. 評価の差分を物理タグに書き込む
py sync_ratings.py --dry-run    # 確認
py sync_ratings.py              # 本番

# 3. ファイル本体の差分も検出して追記
py sync_files.py --apply

# 4. MusicBee 側にミラー (新規曲があるので --create-missing)
py mirror_changed.py --dry-run --create-missing
py mirror_changed.py --create-missing

# 5. MusicBee でライブラリ再スキャン
```

#### B. 評価だけ変えたとき

```powershell
py sync_ratings.py
py mirror_changed.py     # --create-missing 不要
```

#### C. iTunes に新曲を追加しただけ (評価変更なし)

```powershell
py sync_files.py --apply
py mirror_changed.py --create-missing
```

#### D. MusicBee 側が古い気がする (救出)

```powershell
py repair_mirror.py                            # 差分チェック
py repair_mirror.py --apply --include-missing  # 追記
py mirror_changed.py --create-missing
```

#### E. 孤児 (DST にだけある曲) の精査

`sync_files.py --apply` を実行すると `orphan_files.txt` が生成される。手動で確認して、不要ならエクスプローラで削除。自動削除はしない設計。

### MusicBee 側の表示更新

書き込み / コピー後、MusicBee の表示を更新するには:

1. 該当曲を選択 → 右クリック → **「Send To」 → 「Library: Rescan」**
2. または `Ctrl+E` でタグを再読み込み
3. ライブラリ全体: **Edit → Edit Preferences → Library → Scan now**

## ディレクトリ構成

```
star_rate_sync/
├── sync_ratings.py        # iTunes -> ファイルタグ同期
├── mirror_changed.py      # 変更ファイルを別フォルダへミラーコピー
├── verify_tags.py         # 書き込み済みタグの読み戻し検証
├── repair_mirror.py       # state と DST タグの不一致を救出
├── sync_files.py          # ファイル本体の差分同期 (評価非依存)
├── gui.py                 # Tkinter GUI (CLI を subprocess で呼ぶ)
├── start_gui.pyw          # GUI 起動用ランチャー
├── starcore/              # 純粋ロジック (テスト容易)
│   ├── diff.py            # 評価の差分判定
│   ├── file_diff.py       # ファイル本体の差分判定 (mtime+size)
│   ├── paths.py           # src -> dst のパス変換
│   ├── state.py           # sync_state.json の load/save
│   ├── changed_list.py    # changed_files.txt の I/O とマージ
│   ├── tagging.py         # MP3 / M4A への rating 書き込み
│   ├── display.py         # CLI 出力の共通フォーマッタ
│   └── aggregate.py       # 星ラベル・遷移分類のヘルパ
├── tests/                 # pytest テスト
└── docs/                  # 詳細ドキュメント
```

## テスト

```powershell
pip install -r requirements-dev.txt
py -m pytest
```

純粋ロジック (`starcore/*`) は単体テスト済み (110+ ケース)。iTunes COM 部分と実 I/O はテスト対象外 (実環境依存のため、必要に応じて `--dry-run` で確認する)。

## ドキュメント

- [docs/cli.md](docs/cli.md) — 各 CLI の全オプション、出力ファイル、差分仕様、救出フロー
- [docs/internals.md](docs/internals.md) — POPM マッピング / MP4 アトム / COM API / トラブルシューティング
- [docs/gui.md](docs/gui.md) — GUI 内部の仕組みと拡張ポイント

## ライセンス

ライセンス未指定。改変・再配布等を行う場合は事前にご相談ください。
