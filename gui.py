"""star_rate_sync の GUI ランチャー。

既存 CLI (sync_ratings.py / mirror_changed.py / verify_tags.py) を
``subprocess`` 経由で実行し、出力をウィンドウ内のテキスト領域に
リアルタイムで流す Tkinter アプリケーション。

ロジックはすべて CLI 側 (=starcore + 各エントリポイント) に任せ、
GUI は「オプションを集めて argv を組み立てる」「子プロセスの stdout を
読んで表示する」「実行中の状態を管理する」だけに徹する。

仕組みの詳細は ``docs/gui.md`` を参照。
"""
from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, List, Optional


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Windows で subprocess を呼ぶ際、子プロセスの黒いコンソールウィンドウを
# 出さないためのフラグ。Linux / macOS では 0 (=何もしない)。
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# 子プロセスからの 1 サイクルあたりの読み出し間隔 (ms)。
# 短いほどリアルタイム性が上がるが、CPU を食う。
POLL_INTERVAL_MS = 80

# 絵文字対応フォント。Windows なら Segoe UI Emoji がデフォで入っている。
EMOJI_FONT_FAMILY = "Segoe UI Emoji"


# ---------------------------------------------------------------------------
# 子プロセス実行を別スレッドで回すラッパー
# ---------------------------------------------------------------------------
class CommandRunner:
    """``subprocess.Popen`` を別スレッドで起動し、stdout の各行を ``queue`` に流す。

    GUI 本体 (mainloop が回っているメインスレッド) はキューを ``after`` で
    ポーリングするだけにすることで、長時間処理中も UI が固まらない。
    """

    # キューに流す特殊メッセージ (タプルの先頭で種別を識別する)
    MSG_LINE = "line"       # ("line", "stdout の1行")
    MSG_DONE = "done"       # ("done", exit_code: int)
    MSG_ERROR = "error"     # ("error", "エラー内容")

    def __init__(self) -> None:
        self.queue: "queue.Queue[tuple]" = queue.Queue()
        self.process: Optional[subprocess.Popen] = None
        self.thread: Optional[threading.Thread] = None
        self.started_at: Optional[float] = None

    # ----- 状態クエリ -----
    def is_running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def elapsed_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        return time.monotonic() - self.started_at

    # ----- 起動 / 停止 -----
    def start(self, argv: List[str]) -> None:
        """``argv`` を別スレッドで起動する。すでに走っていれば何もしない。"""
        if self.is_running():
            return

        self.queue = queue.Queue()
        self.started_at = time.monotonic()

        # 子プロセスにも UTF-8 を強制する (Windows の cp932 文字化け対策)
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        # PIPE 接続だと stdout がブロックバッファリングされ、ログがまとめて
        # 流れて「動いてないように見える」事故が起きる。env と -u の両方で
        # 確実に unbuffered にする。
        env["PYTHONUNBUFFERED"] = "1"

        self.thread = threading.Thread(
            target=self._run, args=(argv, env), daemon=True
        )
        self.thread.start()

    def stop(self) -> None:
        """実行中の子プロセスを終了させる。

        ``terminate()`` で強制終了するため、タグ書き込みやファイルコピーの
        途中だった曲は中途半端な状態で残る可能性がある。state ファイルが
        壊れたら自動退避され、再実行 (必要なら ``--force-all``) で回復できる。
        """
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass

    # ----- 内部 -----
    def _run(self, argv: List[str], env: dict) -> None:
        try:
            self.process = subprocess.Popen(
                argv,
                cwd=ROOT_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # stderr も同じストリームへ
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                creationflags=CREATE_NO_WINDOW,
                bufsize=1,                 # 行バッファリング
            )
        except Exception as e:
            self.queue.put((self.MSG_ERROR, f"プロセス起動失敗: {e}"))
            self.queue.put((self.MSG_DONE, -1))
            return

        assert self.process.stdout is not None
        try:
            for raw in iter(self.process.stdout.readline, ""):
                # tqdm が \r で進捗を上書きする場合に備えて、改行/CR で分割しておく
                for line in raw.replace("\r", "\n").splitlines():
                    self.queue.put((self.MSG_LINE, line))
        except Exception as e:
            self.queue.put((self.MSG_ERROR, f"読み出し中エラー: {e}"))

        exit_code = self.process.wait()
        self.queue.put((self.MSG_DONE, exit_code))


# ---------------------------------------------------------------------------
# 各タブが提供すべき情報を定義する小さなプロトコル
# ---------------------------------------------------------------------------
class TabSpec:
    """1 つのタブに対応する設定。

    - ``label``:        Notebook 上の表示名
    - ``script``:       実行する Python スクリプト名
    - ``build_options``: そのタブにオプション UI を組み立てる関数
    - ``compose_argv``:  実行時に CLI 引数のリストを返す関数
    """

    def __init__(
        self,
        label: str,
        script: str,
        build_options: Callable[[ttk.Frame], None],
        compose_argv: Callable[[], List[str]],
    ) -> None:
        self.label = label
        self.script = script
        self.build_options = build_options
        self.compose_argv = compose_argv


# ---------------------------------------------------------------------------
# 本体アプリ
# ---------------------------------------------------------------------------
class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("star_rate_sync")
        self.root.geometry("760x600")
        self.root.minsize(560, 420)

        # 既定フォント。絵文字対応フォントを基準にしておくと ✅ ── ★ が出る。
        self.root.option_add("*Font", (EMOJI_FONT_FAMILY, 10))

        self.runner = CommandRunner()

        # ---- 共通状態 (各タブのオプション値) ----
        # 誤操作を避けるため、書き込み系タブは初期状態を dry-run ON にしておく。
        # 実行確認後にチェックを外して本番実行する想定。
        self.var_sync_dry_run = tk.BooleanVar(value=True)
        self.var_sync_force_all = tk.BooleanVar(value=False)
        self.var_sync_detail = tk.BooleanVar(value=False)
        self.var_sync_limit = tk.IntVar(value=0)

        self.var_mirror_dry_run = tk.BooleanVar(value=True)
        self.var_mirror_create_missing = tk.BooleanVar(value=False)

        self.var_verify_limit = tk.IntVar(value=0)

        # ---- UI 構築 ----
        self._build_notebook()
        self._build_run_row()
        self._build_output_area()
        self._build_status_bar()

        # 終了時の後片付け
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- レイアウト ----
    def _build_notebook(self) -> None:
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(side="top", fill="x", padx=12, pady=(12, 6))

        self.tabs: List[TabSpec] = [
            TabSpec("Sync", "sync_ratings.py",
                    self._build_sync_tab, self._compose_sync_argv),
            TabSpec("Mirror", "mirror_changed.py",
                    self._build_mirror_tab, self._compose_mirror_argv),
            TabSpec("Verify", "verify_tags.py",
                    self._build_verify_tab, self._compose_verify_argv),
        ]

        for spec in self.tabs:
            frame = ttk.Frame(self.notebook, padding=12)
            spec.build_options(frame)
            self.notebook.add(frame, text=spec.label)

    def _build_sync_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="iTunes → ファイルタグへ評価を書き込みます",
                  foreground="#555").pack(anchor="w", pady=(0, 8))

        ttk.Checkbutton(parent, text="dry-run (書き込みせず差分だけ表示)",
                        variable=self.var_sync_dry_run).pack(anchor="w")
        ttk.Checkbutton(parent, text="force-all (state をリセットして全評価曲を書き直す)",
                        variable=self.var_sync_force_all).pack(anchor="w")
        ttk.Checkbutton(parent, text="detail (★n → ★m の遷移マップも表示)",
                        variable=self.var_sync_detail).pack(anchor="w")

        row = ttk.Frame(parent)
        row.pack(anchor="w", pady=(6, 0))
        ttk.Label(row, text="limit (0=無制限):").pack(side="left")
        ttk.Entry(row, textvariable=self.var_sync_limit, width=8).pack(side="left", padx=6)

    def _build_mirror_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent,
                  text="changed_files.txt の曲を MusicBee 側フォルダへコピーします",
                  foreground="#555").pack(anchor="w", pady=(0, 8))

        ttk.Checkbutton(parent, text="dry-run (コピーせず予定だけ表示)",
                        variable=self.var_mirror_dry_run).pack(anchor="w")
        ttk.Checkbutton(parent,
                        text="create-missing (コピー先に無いファイルも新規作成)",
                        variable=self.var_mirror_create_missing).pack(anchor="w")

        ttk.Label(parent,
                  text="※ SRC/DST のパスは .env (STAR_RATE_SYNC_SRC_ROOT / _DST_ROOT) で設定",
                  foreground="#999").pack(anchor="w", pady=(8, 0))

    def _build_verify_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent,
                  text="sync_state.json に記録された値と物理タグを照合します",
                  foreground="#555").pack(anchor="w", pady=(0, 8))

        row = ttk.Frame(parent)
        row.pack(anchor="w")
        ttk.Label(row, text="limit (0=全件):").pack(side="left")
        ttk.Entry(row, textvariable=self.var_verify_limit, width=8).pack(side="left", padx=6)

    def _build_run_row(self) -> None:
        row = ttk.Frame(self.root)
        row.pack(side="top", fill="x", padx=12, pady=(0, 6))

        self.btn_run = ttk.Button(row, text="▶  実行", command=self._on_run)
        self.btn_run.pack(side="left")

        self.btn_stop = ttk.Button(row, text="■  停止",
                                   command=self._on_stop, state="disabled")
        self.btn_stop.pack(side="left", padx=(6, 0))

        ttk.Button(row, text="クリア",
                   command=self._on_clear_output).pack(side="right")

    def _build_output_area(self) -> None:
        frame = ttk.Frame(self.root)
        frame.pack(side="top", fill="both", expand=True, padx=12, pady=(0, 6))

        # Text widget は ttk に無いので tk.Text を使う
        self.output = tk.Text(
            frame, wrap="none", height=20,
            font=(EMOJI_FONT_FAMILY, 10),
            background="#1e1e1e", foreground="#e6e6e6",
            insertbackground="#e6e6e6",
        )
        self.output.configure(state="disabled")

        ysb = ttk.Scrollbar(frame, orient="vertical", command=self.output.yview)
        xsb = ttk.Scrollbar(frame, orient="horizontal", command=self.output.xview)
        self.output.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)

        self.output.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

    def _build_status_bar(self) -> None:
        self.status_var = tk.StringVar(value="待機中")
        bar = ttk.Frame(self.root)
        bar.pack(side="bottom", fill="x", padx=12, pady=(0, 8))
        ttk.Label(bar, textvariable=self.status_var,
                  foreground="#555").pack(side="left")

    # ---- argv 構築 ----
    def _compose_sync_argv(self) -> List[str]:
        argv = [sys.executable, "-u", "sync_ratings.py"]
        if self.var_sync_dry_run.get():
            argv.append("--dry-run")
        if self.var_sync_force_all.get():
            argv.append("--force-all")
        if self.var_sync_detail.get():
            argv.append("--detail")
        limit = self.var_sync_limit.get()
        if limit > 0:
            argv += ["--limit", str(limit)]
        return argv

    def _compose_mirror_argv(self) -> List[str]:
        argv = [sys.executable, "-u", "mirror_changed.py"]
        if self.var_mirror_dry_run.get():
            argv.append("--dry-run")
        if self.var_mirror_create_missing.get():
            argv.append("--create-missing")
        return argv

    def _compose_verify_argv(self) -> List[str]:
        argv = [sys.executable, "-u", "verify_tags.py"]
        limit = self.var_verify_limit.get()
        if limit > 0:
            argv += ["--limit", str(limit)]
        return argv

    # ---- ボタンハンドラ ----
    def _on_run(self) -> None:
        if self.runner.is_running():
            return

        spec = self.tabs[self.notebook.index("current")]
        try:
            argv = spec.compose_argv()
        except tk.TclError:
            self._append_output("[error] limit には整数を入力してください\n")
            return

        # 破壊力の大きい操作 (force-all を本番実行) は確認ダイアログを挟む。
        # dry-run が併用されている場合は実害が無いので素通り。
        if (
            spec.script == "sync_ratings.py"
            and self.var_sync_force_all.get()
            and not self.var_sync_dry_run.get()
        ):
            ok = messagebox.askokcancel(
                title="force-all を実行しますか？",
                message=(
                    "state を無視して評価のある曲を全部書き直します。\n"
                    "件数が多いと時間がかかり、書き込み中に中断するとタグが\n"
                    "中途半端になる可能性があります。\n\n"
                    "実行してよろしいですか？"
                ),
                icon=messagebox.WARNING,
                default=messagebox.CANCEL,
            )
            if not ok:
                self._append_output("[info] force-all 実行をキャンセルしました\n")
                return

        self._append_output(
            f"$ {' '.join(_shell_quote(a) for a in argv)}\n"
        )
        self.runner.start(argv)
        self._set_running_ui(True)
        self.root.after(POLL_INTERVAL_MS, self._poll_queue)

    def _on_stop(self) -> None:
        self.runner.stop()
        self.status_var.set("停止中…")

    def _on_clear_output(self) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def _on_close(self) -> None:
        # 実行中なら kill してから閉じる
        self.runner.stop()
        self.root.destroy()

    # ---- メインスレッド側ポーリング ----
    def _poll_queue(self) -> None:
        finished = False
        exit_code = 0

        while True:
            try:
                kind, payload = self.runner.queue.get_nowait()
            except queue.Empty:
                break

            if kind == CommandRunner.MSG_LINE:
                self._append_output(payload + "\n")
            elif kind == CommandRunner.MSG_ERROR:
                self._append_output(f"[error] {payload}\n")
            elif kind == CommandRunner.MSG_DONE:
                finished = True
                exit_code = payload

        elapsed = self.runner.elapsed_seconds()
        if finished:
            self._set_running_ui(False)
            mark = "✅" if exit_code == 0 else "❌"
            self.status_var.set(
                f"{mark} 完了  exit={exit_code}  ({elapsed:.1f}s)"
            )
        else:
            self.status_var.set(f"実行中…  ({elapsed:.1f}s)")
            self.root.after(POLL_INTERVAL_MS, self._poll_queue)

    # ---- helper ----
    def _append_output(self, text: str) -> None:
        self.output.configure(state="normal")
        self.output.insert("end", text)
        self.output.see("end")
        self.output.configure(state="disabled")

    def _set_running_ui(self, running: bool) -> None:
        self.btn_run.configure(state="disabled" if running else "normal")
        self.btn_stop.configure(state="normal" if running else "disabled")


def _shell_quote(s: str) -> str:
    """ログ表示用にスペースを含む引数だけクォートする。実行には使わない。"""
    return f'"{s}"' if " " in s else s


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
