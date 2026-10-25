#!/usr/bin/env python3
"""Small Tkinter interface for extracting and optionally normalizing audio."""
from __future__ import annotations

import queue
import shutil
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from extract_audio import FORMATS, extract, output_for


class AudioExtractorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("音轨提取器")
        self.root.geometry("760x590")
        self.root.minsize(650, 500)

        self.files: list[Path] = []
        self.messages: queue.Queue[tuple] = queue.Queue()
        self.busy = False
        self.format_var = tk.StringVar(value="mp3")
        self.normalize_var = tk.BooleanVar(value=False)
        self.overwrite_var = tk.BooleanVar(value=False)
        self.output_var = tk.StringVar(value=str(Path.home() / "Music" / "音轨提取"))
        self.ffmpeg_var = tk.StringVar(value=shutil.which("ffmpeg") or "ffmpeg")

        self._build_ui()
        self.root.after(100, self._poll_messages)

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        ttk.Label(frame, text="选择录制文件", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        file_area = ttk.Frame(frame)
        file_area.grid(row=1, column=0, sticky="nsew")
        file_area.columnconfigure(0, weight=1)
        file_area.rowconfigure(0, weight=1)
        self.file_list = tk.Listbox(file_area, selectmode=tk.EXTENDED, height=8)
        self.file_list.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(file_area, orient="vertical", command=self.file_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.file_list.configure(yscrollcommand=scrollbar.set)

        file_buttons = ttk.Frame(file_area)
        file_buttons.grid(row=0, column=2, sticky="ns", padx=(10, 0))
        ttk.Button(file_buttons, text="添加文件…", command=self._add_files).pack(fill="x", pady=(0, 6))
        ttk.Button(file_buttons, text="移除选中", command=self._remove_selected).pack(fill="x", pady=3)
        ttk.Button(file_buttons, text="清空列表", command=self._clear_files).pack(fill="x", pady=3)

        options = ttk.LabelFrame(frame, text="提取选项", padding=10)
        options.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        options.columnconfigure(1, weight=1)

        ttk.Label(options, text="输出格式").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        format_box = ttk.Combobox(
            options,
            textvariable=self.format_var,
            values=list(FORMATS),
            state="readonly",
            width=12,
        )
        format_box.grid(row=0, column=1, sticky="w", pady=4)

        normalize_row = ttk.Frame(options)
        normalize_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)
        ttk.Checkbutton(
            normalize_row,
            text="提取后自动归一化响度",
            variable=self.normalize_var,
        ).pack(side="left")
        ttk.Label(normalize_row, text="目标 -16 LUFS，真峰值上限 -1.5 dBTP").pack(
            side="left", padx=(12, 0)
        )

        ttk.Checkbutton(
            options,
            text="覆盖已存在的输出文件",
            variable=self.overwrite_var,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=4)

        ttk.Label(options, text="输出目录").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(options, textvariable=self.output_var).grid(row=3, column=1, sticky="ew", pady=4)
        self.output_button = ttk.Button(options, text="浏览…", command=self._choose_output)
        self.output_button.grid(row=3, column=2, padx=(8, 0), pady=4)

        ttk.Label(options, text="FFmpeg").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(options, textvariable=self.ffmpeg_var).grid(row=4, column=1, sticky="ew", pady=4)
        self.ffmpeg_button = ttk.Button(options, text="选择程序…", command=self._choose_ffmpeg)
        self.ffmpeg_button.grid(row=4, column=2, padx=(8, 0), pady=4)

        footer = ttk.Frame(frame)
        footer.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        footer.columnconfigure(0, weight=1)
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=120)
        self.progress.grid(row=0, column=1, padx=10)
        self.start_button = ttk.Button(footer, text="开始提取", command=self._start)
        self.start_button.grid(row=0, column=2)

        self.log = tk.Text(frame, height=7, wrap="word", state="disabled")
        self.log.grid(row=4, column=0, sticky="ew", pady=(10, 0))

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="选择录制的视频或音频",
            filetypes=[
                ("媒体文件", "*.mp4 *.mkv *.mov *.avi *.webm *.mp3 *.wav *.m4a *.flac *.aac *.ogg *.opus"),
                ("所有文件", "*.*"),
            ],
        )
        for value in paths:
            path = Path(value)
            if path not in self.files:
                self.files.append(path)
                self.file_list.insert(tk.END, str(path))

    def _remove_selected(self) -> None:
        indices = list(self.file_list.curselection())
        for index in reversed(indices):
            self.file_list.delete(index)
            del self.files[index]

    def _clear_files(self) -> None:
        self.files.clear()
        self.file_list.delete(0, tk.END)

    def _choose_output(self) -> None:
        selected = filedialog.askdirectory(title="选择音频输出目录", initialdir=self.output_var.get())
        if selected:
            self.output_var.set(selected)

    def _choose_ffmpeg(self) -> None:
        selected = filedialog.askopenfilename(
            title="选择 FFmpeg 可执行文件",
            filetypes=[("FFmpeg", "ffmpeg.exe"), ("所有文件", "*.*")],
        )
        if selected:
            self.ffmpeg_var.set(selected)

    def _append_log(self, line: str) -> None:
        self.log.configure(state="normal")
        self.log.insert(tk.END, line + "\n")
        self.log.see(tk.END)
        self.log.configure(state="disabled")

    def _start(self) -> None:
        if self.busy:
            return
        if not self.files:
            messagebox.showinfo("需要选择文件", "请先添加一个或多个录制文件。")
            return

        ffmpeg = self.ffmpeg_var.get().strip()
        if ffmpeg == "ffmpeg":
            ffmpeg = shutil.which(ffmpeg) or ""
        elif not Path(ffmpeg).is_file():
            ffmpeg = ""
        if not ffmpeg:
            messagebox.showerror("找不到 FFmpeg", "请安装 FFmpeg 并加入 PATH，或用“选择程序…”指定 ffmpeg.exe。")
            return

        output_dir = Path(self.output_var.get()).expanduser()
        if not str(output_dir).strip():
            messagebox.showerror("缺少输出目录", "请选择音频输出目录。")
            return

        self.busy = True
        self.start_button.configure(state="disabled")
        self.output_button.configure(state="disabled")
        self.ffmpeg_button.configure(state="disabled")
        self.progress.start(12)
        self.status_var.set("处理中…")
        threading.Thread(
            target=self._process_files,
            args=(list(self.files), output_dir, self.format_var.get(), self.normalize_var.get(), self.overwrite_var.get(), ffmpeg),
            daemon=True,
        ).start()

    def _process_files(
        self,
        files: list[Path],
        output_dir: Path,
        output_format: str,
        normalize: bool,
        overwrite: bool,
        ffmpeg: str,
    ) -> None:
        succeeded = 0
        failed = 0
        for index, source in enumerate(files, start=1):
            target = output_for(source, output_dir, output_format)
            self.messages.put(("status", f"处理中 {index}/{len(files)}：{source.name}"))
            if source.resolve() == target.resolve(strict=False):
                failed += 1
                self.messages.put(("log", f"失败（输入和输出路径相同）：{source}"))
                continue
            if target.exists() and not overwrite:
                failed += 1
                self.messages.put(("log", f"已跳过（目标已存在）：{target.name}"))
                continue
            try:
                ok = extract(
                    ffmpeg,
                    source,
                    target,
                    output_format,
                    overwrite,
                    normalize=normalize,
                )
            except Exception as exc:
                failed += 1
                self.messages.put(("log", f"处理出错：{source}（{exc}）"))
                continue
            if ok:
                succeeded += 1
                self.messages.put(("log", f"完成：{target}"))
            else:
                failed += 1
                self.messages.put(("log", f"失败：{source}"))
        self.messages.put(("done", succeeded, failed))

    def _poll_messages(self) -> None:
        try:
            while True:
                message = self.messages.get_nowait()
                if message[0] == "status":
                    self.status_var.set(message[1])
                elif message[0] == "log":
                    self._append_log(message[1])
                elif message[0] == "done":
                    _, succeeded, failed = message
                    self.busy = False
                    self.progress.stop()
                    self.start_button.configure(state="normal")
                    self.output_button.configure(state="normal")
                    self.ffmpeg_button.configure(state="normal")
                    self.status_var.set(f"完成：成功 {succeeded}，失败或跳过 {failed}")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_messages)


def main() -> None:
    root = tk.Tk()
    AudioExtractorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
