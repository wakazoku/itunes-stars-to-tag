# GUI の仕組みメモ

`gui.py` / `start_gui.pyw` の設計と、後から手を入れるときに知っておきたい
ポイントをまとめたメモ。普段使いの操作方法は README の「GUI」セクション参照。

## 1. 全体方針

- **GUI は薄いガワに徹する**: 評価の読み書きや差分検出のロジックは一切
  GUI 側に持たせない。`gui.py` がやるのは次の 3 つだけ。
  1. オプション (チェックボックス・数値入力) を画面に出す
  2. CLI 引数を組み立てて `subprocess.Popen` で既存スクリプトを叩く
  3. 子プロセスの標準出力をテキスト領域へ流し込む
- これによって、CLI に新しい機能を足したら GUI 側はオプションを足すだけで
  済む。逆に GUI を作り直したくなっても、`starcore` と CLI 群は無傷。
- 配布は想定しない。`pip install -r requirements.txt` 済みの環境で
  `start_gui.pyw` をダブルクリックすれば立ち上がる。

## 2. ファイル構成

```
gui.py            … Tkinter 本体 (CommandRunner / App)
start_gui.pyw     … ダブルクリック起動用のランチャー (.pyw)
docs/gui.md       … この文書
```

`.pyw` は Windows で `pythonw.exe` に紐付いていて、黒いコンソールウィンドウ
を出さずに GUI だけを立ち上げる拡張子。中身は `from gui import main` を
呼ぶだけのワンライナー。

## 3. アーキテクチャ

```
┌────────────────────────────────────────────┐
│ メインスレッド (Tk mainloop)               │
│                                            │
│  Notebook ─┬─ Sync タブ (オプション群)     │
│            ├─ Mirror タブ                  │
│            └─ Verify タブ                  │
│                                            │
│  [▶ 実行] / [■ 停止] / [クリア]            │
│                                            │
│  ┌──── Text (stdout 表示) ────┐            │
│  │ ✅ 書き込み成功: 12 件 ... │            │
│  └────────────────────────────┘            │
│                                            │
│  ステータスバー (経過秒・終了コード)       │
└────────────┬───────────────────────────────┘
             │ root.after(POLL_INTERVAL_MS) で
             │ ポーリングして queue を吸い出す
             ▼
        ┌────────────┐
        │ queue.Queue │   ← ("line", str) / ("done", exit_code)
        └────┬────────┘
             ▲ put_nowait
┌────────────┴───────────────────────────────┐
│ ワーカースレッド (threading.Thread)        │
│                                            │
│  subprocess.Popen([                        │
│    sys.executable, "sync_ratings.py", ...] │
│  )                                         │
│  for line in stdout.readline:              │
│      queue.put(("line", line))             │
│  queue.put(("done", exit_code))            │
└────────────────────────────────────────────┘
```

要するに **「スレッドを 1 本掘って Popen → readline ループ → queue に
詰める」「メインスレッドは `after` で queue を吸って Text に貼る」** という
Tkinter で長時間処理を扱うときの定型パターン。

### なぜスレッドが必要か

`Popen.stdout.readline()` はデータが来るまでブロックするので、メインスレッド
(=mainloop が回っているスレッド) で直接呼ぶと GUI がそのまま固まる。
別スレッドに逃がしたうえで、GUI 側は `after` で軽くポーリングする。

### なぜ Queue を挟むか

Tkinter のウィジェットはメインスレッド以外から触ると壊れる (描画が崩れたり
Tcl_AsyncDelete が出たり)。ワーカースレッドから直接 `text.insert` できない
ので、`queue.Queue` (スレッドセーフ) に行を投げ、メインスレッドが受け取って
ウィジェットを更新する。

## 4. 主要クラス

### `CommandRunner` (gui.py)

`subprocess` ラッパー。
状態管理を 1 か所に閉じておくと、後で「進捗バーを足したい」「ログを
ファイルにも残したい」となったときの手数が少なくなる。

- `start(argv)` … スレッド起動。すでに走っていれば no-op
- `stop()` … `process.terminate()` で停止依頼
- `is_running()` / `elapsed_seconds()` … メインスレッドからの状態クエリ
- 内部の `_run()` だけが別スレッドで動く

子プロセスには `PYTHONIOENCODING=utf-8` と `PYTHONUTF8=1` を渡している。
これを忘れると Windows の cp932 で再び絵文字が化ける。
加えて `PYTHONUNBUFFERED=1` と `python -u` の両方で stdout の
バッファリングを切っている。`subprocess.PIPE` 接続時のデフォルトは
ブロックバッファリングで、これを切らないと処理完了までログが
まとめて流れる (=「動いてないように見える」事故が起きる)。

### `App` (gui.py)

UI 構築 + イベントハンドラ。
タブの追加は `self.tabs` の `TabSpec` リストを増やすだけで済むように
してある。CLI を 1 本追加したくなったときは:

1. オプション用の `tk.BooleanVar` / `tk.IntVar` を `__init__` に追加
2. `_build_xxx_tab` を 1 つ書く (オプションを並べるだけ)
3. `_compose_xxx_argv` を 1 つ書く (argv を組み立てるだけ)
4. `self.tabs` に `TabSpec(...)` を 1 行足す

## 5. デザイン上の小ネタ

- **絵文字フォント**: 既定フォントを `Segoe UI Emoji` にしている。
  これがないと `✅ ❌ ★` が豆腐になる。Linux で動かすときは
  `Noto Color Emoji` などに差し替える。
- **ダークな出力エリア**: `tk.Text` の背景を `#1e1e1e` にしただけ。
  ターミナルっぽく見えると安心感がある。
- **tqdm 等の `\r` 上書き表示**: 受け取った行を
  `replace("\r", "\n").splitlines()` で噛み砕いてからキューに入れる。
  もし生 tqdm を綺麗に再現したくなったらこの辺りを書き換えるか、
  CLI 側で `TQDM_DISABLE=1` を渡してテキストモードに固定する。
- **`force-all` の確認ダイアログ**: `Sync` タブで `force-all` を ON のまま
  本番実行 (dry-run OFF) しようとした場合のみ、`tkinter.messagebox` で
  確認を入れる。dry-run 併用なら実害が無いので素通り。
- **「停止」ボタン**: `process.terminate()` を呼ぶだけの強制終了。
  ちょうど書き込み中の曲があった場合、その曲のタグは中途半端な状態で
  残る可能性がある。`sync_state.json` 自体は書き込み中に壊れても自動
  退避されるので、再実行 (必要なら `--force-all`) で復旧できる。
  「絶対に壊れない」わけではないので過信しないこと。
- **ウィンドウを閉じたとき**: `WM_DELETE_WINDOW` をフックして実行中の
  子プロセスを kill してから `destroy()` する。子プロセスが
  ぶら下がるのを防ぐため。

## 6. 拡張案メモ

- **ログを `sync_log.txt` 等のファイルにも吐く**: `_append_output` で
  Text に書くついでに `open(..., "a")` で同じ内容を書き込めばよい。
- **進捗バー (`ttk.Progressbar`)**: 現状 CLI 出力からは件数を抜きにくい。
  CLI 側に `--progress-json` のようなオプションを足し、JSON Lines で
  進捗を吐かせると素直。
- **コマンド履歴 / プリセット保存**: 最後に使ったオプションを
  `~/.star_rate_sync/gui.json` に保存してもいい。
- **配布したくなったら**: PyInstaller で `start_gui.pyw` をバンドル
  すれば exe になる。ただし MusicBee / iTunes との依存があるので
  配布相手が同じ Windows ユーザーに限られる点に注意。
