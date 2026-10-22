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

- **普段の運用**: 書込、ファイル差分、コピーを続けて実行
- **評価同期**: 書込 / コピー / 検証 / 救出
- **ファイル同期**: 差分

各タブ内に `CLI: py ...` の一行と操作の目安が表示される。旧称との対応: 書込=`sync_ratings.py`、コピー=`mirror_changed.py`、検証=`verify_tags.py`、救出=`repair_mirror.py`、差分=`sync_files.py`。

書き込み系タブは初期状態で **dry-run が ON**。一度確認してからチェックを外して本番実行する。

詳細は [docs/gui.md](docs/gui.md)。

#### GUI シナリオ集

下記の CLI シナリオ集 (A〜E) を GUI でやる場合の操作手順。
各ステップで「dry-run を一度実行 → 出力確認 → 本番実行」を挟むのが安全。

##### A. 普段の運用 (評価 + ファイル本体を両方同期)

GUI なら `[普段の運用] > まとめて` で同じ 3 段階を実行できる。
apply は初期 OFF。件数を見てから ON にする。

段階を分ける場合:

1. iTunes を起動しておく
2. `[評価同期] > 書込` タブ → dry-run のまま「▶ 実行」→ 件数確認 → dry-run チェックを外して再実行
3. `[ファイル同期] > 差分` タブ → 「▶ 実行」(dry-run) → 件数確認 → `apply` ON で再実行
4. `[評価同期] > コピー` タブ → `create-missing` ON、dry-run のまま「▶ 実行」→ dry-run チェックを外して再実行
5. MusicBee でライブラリ再スキャン

##### B. 評価だけ変えたとき

1. `[評価同期] > 書込` → dry-run 確認 → 本番実行
2. `[評価同期] > コピー` → dry-run 確認 → 本番実行 (`create-missing` は OFF のままで OK)

##### C. iTunes に新曲を追加しただけ (評価変更なし)

1. `[ファイル同期] > 差分` → dry-run 確認 → `apply` ON で実行
2. `[評価同期] > コピー` → `create-missing` ON で実行

##### D. MusicBee 側が古い気がする (救出)

1. `[評価同期] > 救出` → dry-run のまま「▶ 実行」→ ズレ件数を確認
2. 同タブで `apply` ON + `include-missing` ON にして再実行
3. `[評価同期] > コピー` → `create-missing` ON で実行

##### E. 孤児 (DST にだけある曲) の精査

`[ファイル同期] > 差分` を `apply` ON で実行すると、リポジトリ直下に `orphan_files.txt` が生成される。
iTunes (SRC) に同じパスが無いファイルの一覧。**検出のみ**で、削除は自動では行わない。

削除する場合 (iTunes が正とみなす運用):

```powershell
py cleanup_duplicates.py --from-list orphan_files.txt          # dry-run
py cleanup_duplicates.py --from-list orphan_files.txt --apply  # 本番削除
```

##### F. iTunes 整理後の重複・孤児クリーンアップ

iTunes の「ライブラリの整理」等でフォルダ名が変わると、MusicBee 側に**同じ曲の古いコピー**が残ることがある。
**孤児** (パス不一致) と **重複** (内容がバイト完全一致) は別概念 (詳細は [docs/internals.md](docs/internals.md))。

1. `[ファイル同期] > 差分` → dry-run で孤児件数を確認 → `apply` ON で `orphan_files.txt` 出力
2. 重複リストを用意する (`find_duplicates.py` は未実装。現状は手動分析または将来の整理タブ)
3. `py cleanup_duplicates.py --from-list <リスト> --apply` で削除
4. MusicBee でライブラリ再スキャン

> 重複の自動検出・GUI からの削除は今後追加予定。差分タブ脚注にも CLI 名が記載されている。

### CLI シナリオ集

#### A. 普段の運用 (評価 + ファイル本体を両方同期)

評価変更、新曲追加、タグ編集、を一気に MusicBee へ反映する。
次の 1 コマンドが、下の 3 段階 (書込 → ファイル差分 → コピー) を順に実行する。
途中で失敗したらそこで止まる。既定は dry-run。

```powershell
py sync_routine.py            # 確認
py sync_routine.py --apply    # 本番
```

段階を分けて実行する場合:

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

`sync_files.py --apply` を実行すると `orphan_files.txt` が生成される。削除は次の CLI:

```powershell
py cleanup_duplicates.py --from-list orphan_files.txt --apply
```

#### F. iTunes 整理後の重複・孤児クリーンアップ

```powershell
# 1. 孤児の検出
py sync_files.py                    # dry-run (件数確認)
py sync_files.py --apply            # orphan_files.txt 出力

# 2. 孤児削除 (明示確認のうえ)
py cleanup_duplicates.py --from-list orphan_files.txt --apply

# 3. 内容完全一致の重複削除 (リストが用意できている場合)
py cleanup_duplicates.py --from-list reports/duplicate_delete_candidates.txt --apply

# 4. MusicBee でライブラリ再スキャン
```

重複リストの自動生成 (`find_duplicates.py`) は未実装。孤児と重複の違いは [docs/internals.md](docs/internals.md) 参照。

### MusicBee 側の表示更新

書き込み / コピー後、MusicBee の表示を更新するには:

1. 該当曲を選択 → 右クリック → **「Send To」 → 「Library: Rescan」**
2. または `Ctrl+E` でタグを再読み込み
3. ライブラリ全体: **Edit → Edit Preferences → Library → Scan now**

## ディレクトリ構成

```
star_rate_sync/
├── sync_routine.py        # 書込 → ファイル差分 → コピー
├── sync_ratings.py        # iTunes -> ファイルタグ同期
├── mirror_changed.py      # 変更ファイルを別フォルダへミラーコピー
├── verify_tags.py         # 書き込み済みタグの読み戻し検証
├── repair_mirror.py       # state と DST タグの不一致を救出
├── sync_files.py          # ファイル本体の差分同期 (評価非依存)
├── cleanup_duplicates.py  # リスト指定の重複/孤児ファイル削除 (検出は別)
├── gui.py                 # Tkinter GUI (CLI を subprocess で呼ぶ)
├── start_gui.pyw          # GUI 起動用ランチャー
├── starcore/              # 純粋ロジック (テスト容易)
│   ├── diff.py            # 評価の差分判定
│   ├── file_diff.py       # ファイル本体の差分判定 (mtime+size)
│   ├── paths.py           # src -> dst のパス変換
│   ├── routine.py         # 普段の運用の実行順
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
