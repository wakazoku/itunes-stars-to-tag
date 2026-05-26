# CLI リファレンス

各スクリプトのコマンドラインオプションと、生成される中間ファイルの仕様。
基本的な使い方は [../README.md](../README.md) のシナリオ集を参照。

## `sync_ratings.py`

iTunes COM 経由で星評価を読み、各曲の物理タグへ書き込む。
差分のみ処理し、変更ファイルを `changed_files.txt` に追記する。

| オプション | 説明 |
|---|---|
| (なし) | `sync_state.json` を見て **差分 (new / modified / removed) だけ** 書き込み |
| `--dry-run` | 書き込みせず差分対象だけ表示。本番前の確認用 |
| `--limit N` | 差分が N 件に達した時点で停止。少量テスト用 |
| `--force-all` | state を無視して全評価曲を書き直す。state も上書きされる |
| `--changed-out PATH` | 変更ファイル一覧の出力先 (既定: `changed_files.txt`) |
| `--detail` | rating 遷移マップ (`★n → ★m が何曲`) も表示する |

`--resume` は廃止。`sync_state.json` による差分検出が常時 ON のため、同じ役目がデフォルト動作に吸収されている。

## `mirror_changed.py`

`changed_files.txt` に並んだファイルを SRC_ROOT → DST_ROOT で対応付け直してコピーする。

| オプション | 既定値 | 説明 |
|---|---|---|
| `--src-root PATH` | `.env` の `STAR_RATE_SYNC_SRC_ROOT` | iTunes 側 (コピー元) のルート |
| `--dst-root PATH` | `.env` の `STAR_RATE_SYNC_DST_ROOT` | MusicBee 側 (コピー先) のルート |
| `--list PATH` | `changed_files.txt` | コピー対象ファイル一覧 |
| `--dry-run` | off | コピーせず予定だけ表示 |
| `--create-missing` | off | コピー先に同名ファイルが無くても、親フォルダごと作って新規コピーする |

パスの解決順:

1. CLI 引数 (`--src-root` / `--dst-root`) が最優先
2. `.env` の `STAR_RATE_SYNC_SRC_ROOT` / `STAR_RATE_SYNC_DST_ROOT`
3. それも未指定ならエラー (exit code 2)

> **デフォルト動作**: コピー先にファイルが無い場合は **スキップしてログに残す** (=「フォルダ構造のズレ」を検出しやすい)。新規大量コピーしたい時のみ `--create-missing` を指定。

## `repair_mirror.py`

「iTunes → ファイルタグ書き込みは成功したが、MusicBee 側へのコピーが取りこぼされた」ケースを救出するためのツール。
`sync_state.json` を真として、MusicBee 側ファイルのタグを直接読み戻し、ズレている曲を `changed_files.txt` に追記する。あとは `mirror_changed.py` で再コピーすれば直る。

| オプション | 既定値 | 説明 |
|---|---|---|
| `--state PATH` | `sync_state.json` | 真として参照する state ファイル |
| `--src-root PATH` | `.env` の `STAR_RATE_SYNC_SRC_ROOT` | iTunes 側ルート |
| `--dst-root PATH` | `.env` の `STAR_RATE_SYNC_DST_ROOT` | MusicBee 側ルート |
| `--changed-out PATH` | `changed_files.txt` | 追記先 |
| `--apply` | off | OFF なら dry-run (表示のみ)。ON で追記する |
| `--include-missing` | off | DST にまだファイルが無い曲も救出対象に含める。Mirror 側で `--create-missing` 併用が必要 |

## `sync_files.py`

**評価とは独立** に、SRC と DST のファイル本体を **mtime + size** で比較し、`new` (DST に無い) と `updated` (mtime/size が違う) を `changed_files.txt` に追記する。あとは `mirror_changed.py --create-missing` で実コピーすれば、星評価が付いていない曲も含めて MusicBee 側に揃う。

孤児 (DST にあるが SRC に無いファイル) は **削除せず** `orphan_files.txt` にレポートのみ。

| オプション | 既定値 | 説明 |
|---|---|---|
| `--src-root PATH` | `.env` の `STAR_RATE_SYNC_SRC_ROOT` | iTunes 側ルート |
| `--dst-root PATH` | `.env` の `STAR_RATE_SYNC_DST_ROOT` | MusicBee 側ルート |
| `--changed-out PATH` | `changed_files.txt` | 追記先 |
| `--orphan-out PATH` | `orphan_files.txt` | 孤児レポートの出力先 |
| `--apply` | off | OFF なら dry-run。ON で追記＆孤児出力 |
| `--no-include-new` | off | 新規 (DST に無い) を追記対象から外す |
| `--no-include-updated` | off | 更新 (mtime/size 差) を追記対象から外す |
| `--mtime-tolerance N` | `1.0` | mtime 一致とみなす誤差秒数 (FAT32 等は `2.0` 推奨) |

差分判定の仕組み:

- **mtime + size 一致** → 同一 (same)
- **size 違い** → 内容が違う (updated)
- **mtime 違い (許容超過)** → 内容が違う疑い (updated)
- mtime 許容秒数はファイルシステムまたぎの誤差吸収用

> rsync のデフォルト判定方式と同じ発想。ハッシュ比較ではないので「同じ mtime/size で中身だけ違う」極めて稀なケースは検出できない点に注意。

## `verify_tags.py`

書き込み済みファイルのタグを読み戻して、`sync_state.json` の値と一致するかを検証する。iTunes COM は使わないので iTunes 未起動でも実行可。

| オプション | 既定値 | 説明 |
|---|---|---|
| `--state PATH` | `sync_state.json` | 検証対象の state ファイル |
| `--limit N` | `0` (全件) | 検証件数の上限 |
| `--output PATH` | `verify_output.txt` | 検証結果の出力先 |

---

## 出力ファイル

実行すると以下のファイルがカレントディレクトリに生成される (`.gitignore` で無視される)。

| ファイル | 出力元 | 内容 |
|---|---|---|
| `sync_state.json` | `sync_ratings.py` | PID → `{ rating, path }`。差分判定のための「前回値」 |
| `sync_state.json.broken` | `sync_ratings.py` | JSON が破損していた場合の自動退避先 |
| `changed_files.txt` | `sync_ratings.py` / `mirror_changed.py` / `repair_mirror.py` / `sync_files.py` | 変更があった曲の絶対パス一覧。`sync_ratings.py` は **既存内容に追記マージ** (`--force-all` のときのみ上書き)、`mirror_changed.py` の本番実行後はコピー成功ぶんが取り除かれる、`repair_mirror.py --apply` / `sync_files.py --apply` はズレ・差分のあるパスを追記する |
| `orphan_files.txt` | `sync_files.py` | DST 側にあるが SRC 側に無いファイルの一覧。レポートのみで削除は行われない |
| `sync_log.txt` | `sync_ratings.py` | スキップ・失敗の詳細ログ |
| `mirror_log.txt` | `mirror_changed.py` | コピー失敗・コピー先不在の詳細ログ |
| `verify_output.txt` | `verify_tags.py` | タグ読み戻し検証結果 |

> 旧 `sync_progress.json` (PID リスト) は新仕様では使われない。残っていても無視されるので、不要なら削除して構わない。

## 差分検出の仕組み (`sync_ratings.py`)

実行のたびに、各曲を次の 4 通りに分類する。

| 分類 | 条件 | 動作 |
|---|---|---|
| `new` | 前回 state に無し（または `rating == 0`）で、iTunes 側が 1 以上 | タグへ書き込み、`changed_files.txt` に追加 |
| `modified` | 前回値と異なる（双方 1 以上） | タグへ上書き、`changed_files.txt` に追加 |
| `removed` | 前回 1 以上、iTunes 側で 0 (=星を外した) | タグを削除し state からも削除、`changed_files.txt` に追加 |
| `none` | 変化なし | 何もしない |

これにより、二回目以降の実行は **iTunes 側で変わった曲だけ** 触る。MusicBee 側へのコピー量も最小限になる。

## 「state が信用できない」ときの逃げ道

| 手段 | 方法 | 効果 |
|---|---|---|
| 全件強制再書き込み | `py sync_ratings.py --force-all` | state を無視して全評価曲を書き直し、state を上書きする |
| state リセット | `del sync_state.json` してから普通に実行 | 全評価曲が `new` 扱い |
| 特定曲だけ復旧 | `sync_state.json` を開いて該当 PID 行を削除 | 次回その曲だけ `new` 扱い |

`sync_state.json` が JSON として壊れていた場合は **自動で `.broken` にリネームされ、空 state で続行** される。詰むことはない。
