import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import yt_dlp  # pip install yt-dlp

QUALITY = {
    "Лучшее качество (mp4)": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]",
    "720p": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
    "480p": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]",
    "Только звук (mp3)": "bestaudio/best",
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YouTube Downloader")

        # Принудительно поднять окно и забрать фокус (фикс --noconsole на Windows)
        self.lift()
        self.attributes('-topmost', True)
        self.after(100, lambda: self.attributes('-topmost', False))
        self.focus_force()
        self.geometry("640x280")
        self.resizable(False, False)
        self.columnconfigure(0, weight=1)

        ttk.Label(self, text="Ссылка на видео:").grid(row=0, column=0, sticky="w", padx=10, pady=(12, 2))
        self.url_entry = ttk.Entry(self)
        self.url_entry.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10)
        self.url_entry.focus()

        # Ручная обработка Ctrl+V (обход бага --noconsole на Windows)
        def paste_from_clipboard(event=None):
            try:
                text = self.clipboard_get()
                if self.url_entry.selection_present():
                    self.url_entry.delete("sel.first", "sel.last")
                self.url_entry.insert(tk.INSERT, text)
            except tk.TclError:
                pass
            return "break"

        def copy_selection(event=None):
            try:
                if self.url_entry.selection_present():
                    self.clipboard_clear()
                    self.clipboard_append(self.url_entry.get("sel.first", "sel.last"))
            except tk.TclError:
                pass
            return "break"

        def cut_selection(event=None):
            try:
                if self.url_entry.selection_present():
                    self.clipboard_clear()
                    self.clipboard_append(self.url_entry.get("sel.first", "sel.last"))
                    self.url_entry.delete("sel.first", "sel.last")
            except tk.TclError:
                pass
            return "break"

        # Биндинг горячих клавиш
        self.url_entry.bind('<Control-v>', paste_from_clipboard)
        self.url_entry.bind('<Control-V>', paste_from_clipboard)
        self.url_entry.bind('<Control-c>', copy_selection)
        self.url_entry.bind('<Control-C>', copy_selection)
        self.url_entry.bind('<Control-x>', cut_selection)
        self.url_entry.bind('<Control-X>', cut_selection)

        # Контекстное меню по правой кнопке мыши
        def show_context_menu(event):
            menu = tk.Menu(self, tearoff=0)
            menu.add_command(label="Вставить", command=paste_from_clipboard)
            menu.add_command(label="Копировать", command=copy_selection)
            menu.add_command(label="Вырезать", command=cut_selection)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        self.url_entry.bind('<Button-3>', show_context_menu)

        ttk.Label(self, text="Качество:").grid(row=2, column=0, sticky="w", padx=10, pady=(8, 2))
        self.quality = ttk.Combobox(self, values=list(QUALITY), state="readonly", width=28)
        self.quality.current(0)
        self.quality.grid(row=3, column=0, sticky="w", padx=10)

        self.folder = os.path.join(os.path.expanduser("~"), "Downloads")
        ttk.Button(self, text="Папка сохранения...", command=self.choose_folder)\
            .grid(row=3, column=1, sticky="e", padx=10)
        self.folder_label = ttk.Label(self, text=f"Сохранять в: {self.folder}")
        self.folder_label.grid(row=4, column=0, columnspan=2, sticky="w", padx=10)

        self.progress = ttk.Progressbar(self, maximum=100)
        self.progress.grid(row=5, column=0, columnspan=2, sticky="ew", padx=10, pady=(12, 4))

        self.status = ttk.Label(self, text="Готово к работе")
        self.status.grid(row=6, column=0, columnspan=2, sticky="w", padx=10)

        self.download_btn = ttk.Button(self, text="Скачать", command=self.start_download)
        self.download_btn.grid(row=7, column=0, columnspan=2, pady=10)

    def choose_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.folder = path
            self.folder_label.config(text=f"Сохранять в: {path}")

    def set_status(self, text):
        self.status.config(text=text)

    def set_progress(self, value):
        self.progress["value"] = value

    def start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("YouTube Downloader", "Вставьте ссылку на видео")
            return
        self.download_btn.config(state="disabled")
        threading.Thread(target=self.download, args=(url,), daemon=True).start()

    def progress_hook(self, d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes", 0)
            pct = done / total * 100 if total else 0
            speed = (d.get("speed") or 0) / 1_000_000
            self.after(0, self.set_progress, pct)
            self.after(0, self.set_status, f"Скачивание: {pct:.0f}%  ({speed:.2f} МБ/с)")
        elif d["status"] == "finished":
            self.after(0, self.set_status, "Обработка (склейка / конвертация)...")

    def download(self, url):
        opts = {
            "outtmpl": os.path.join(self.folder, "%(title)s.%(ext)s"),
            "noplaylist": True,
            "progress_hooks": [self.progress_hook],
        }
        # если ffmpeg.exe лежит рядом с программой — используем его
        exe_dir = os.path.dirname(sys.executable)
        if os.path.exists(os.path.join(exe_dir, "ffmpeg.exe")):
            opts["ffmpeg_location"] = exe_dir

        if self.quality.get() == "Только звук (mp3)":
            opts["format"] = QUALITY[self.quality.get()]
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "codec": "mp3",
                "preferredquality": "192",
            }]
        else:
            opts["format"] = QUALITY[self.quality.get()]
            opts["merge_output_format"] = "mp4"

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", url)
            self.after(0, self.set_progress, 100)
            self.after(0, self.set_status, f"Готово: {title}")
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Ошибка", str(e)))
            self.after(0, self.set_status, "Ошибка")
        finally:
            self.after(0, lambda: self.download_btn.config(state="normal"))


if __name__ == "__main__":
    App().mainloop()
