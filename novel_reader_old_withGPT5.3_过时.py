import os
import re
import json
import hashlib
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import chardet
except Exception:
    chardet = None

APP_NAME = "PC小说阅读器"
APP_DIR_NAME = "NovelReader"
CONFIG_FILE = "reader_state.json"

ENCODINGS = [
    "utf-8",
    "utf-8-sig",
    "gbk",
    "gb2312",
    "gb18030",
    "big5",
    "latin-1",
]

DEFAULT_RULE = r"^(第[〇零一二三四五六七八九十百千万0-9]+[章节回卷篇].*|Chapter\s+[0-9IVXLCivxlc]+.*)$"


def get_app_data_dir():
    # 优先使用 APPDATA，便于 exe 运行和权限管理；其次回退到用户目录
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def safe_basename(path):
    try:
        return os.path.basename(path)
    except Exception:
        return "未命名文件"


class ReaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1240x780")
        self.root.minsize(900, 600)

        self.app_data_dir = get_app_data_dir()
        self.config_path = os.path.join(self.app_data_dir, CONFIG_FILE)

        # 文件/内容状态
        self.current_file = None
        self.file_id = None
        self.raw_bytes = b""
        self.loaded_encoding = None

        # 大文件优化：行缓存 + 章节索引（行号）
        self.lines = []  # list[str]
        self.chapters = []  # list[dict]: {title, start_line, end_line, char_len}
        self.chapter_prefix_chars = []  # 前缀和：chapter_prefix_chars[i] = 章节 i 起始字符位置
        self.total_chars = 0

        self.current_chapter_idx = 0
        self.current_chapter_dirty = False
        self.edited_chapter_text = {}  # idx -> edited string
        self.unsaved = False
        self.is_edit_mode = False
        self.is_updating_ui = False

        self.state = self.load_state()

        self.encoding_var = tk.StringVar(value="auto")
        self.rule_var = tk.StringVar(value=self.state.get("chapter_rule", DEFAULT_RULE))
        self.theme_var = tk.StringVar(value=self.state.get("theme", "warm"))
        self.font_size_var = tk.IntVar(value=self.state.get("font_size", 16))
        self.line_spacing_var = tk.DoubleVar(value=self.state.get("line_spacing", 1.8))

        self.progress_text = tk.StringVar(value="全文 0.0% | 本章 0.0%")
        self.status_text = tk.StringVar(value="就绪")

        self.sidebar_visible = True
        self._progress_job = None
        self._open_job = None

        self._build_ui()
        self.apply_theme(self.theme_var.get())
        self.bind_hotkeys()
        self.update_title()

    # -------------------- 状态存储 --------------------
    def load_state(self):
        if not os.path.exists(self.config_path):
            return {"files": {}, "chapter_rule": DEFAULT_RULE, "theme": "warm", "font_size": 16, "line_spacing": 1.8}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("invalid state")
            data.setdefault("files", {})
            data.setdefault("chapter_rule", DEFAULT_RULE)
            data.setdefault("theme", "warm")
            data.setdefault("font_size", 16)
            data.setdefault("line_spacing", 1.8)
            return data
        except Exception:
            return {"files": {}, "chapter_rule": DEFAULT_RULE, "theme": "warm", "font_size": 16, "line_spacing": 1.8}

    def save_state(self):
        self.state["chapter_rule"] = self.rule_var.get()
        self.state["theme"] = self.theme_var.get()
        self.state["font_size"] = self.font_size_var.get()
        self.state["line_spacing"] = self.line_spacing_var.get()
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.set_status(f"保存配置失败: {e}")

    # -------------------- UI --------------------
    def _build_ui(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        top = ttk.Frame(self.root)
        top.pack(fill=tk.X, padx=8, pady=6)

        self.sidebar_btn = ttk.Button(top, text="目录 ◀", command=self.toggle_sidebar)
        self.sidebar_btn.pack(side=tk.LEFT, padx=3)

        ttk.Button(top, text="打开TXT", command=self.open_file).pack(side=tk.LEFT, padx=3)
        ttk.Button(top, text="保存", command=self.save_file).pack(side=tk.LEFT, padx=3)
        ttk.Button(top, text="另存为", command=self.save_as).pack(side=tk.LEFT, padx=3)
        ttk.Button(top, text="编辑(E)", command=self.toggle_edit).pack(side=tk.LEFT, padx=3)

        ttk.Label(top, text="编码:").pack(side=tk.LEFT, padx=(14, 3))
        self.encoding_box = ttk.Combobox(top, textvariable=self.encoding_var, width=12, state="readonly")
        self.encoding_box["values"] = ["auto"] + ENCODINGS
        self.encoding_box.pack(side=tk.LEFT)
        self.encoding_box.bind("<<ComboboxSelected>>", lambda e: self.reload_with_selected_encoding())

        ttk.Label(top, text="章节规则:").pack(side=tk.LEFT, padx=(14, 3))
        self.rule_entry = ttk.Entry(top, textvariable=self.rule_var, width=34)
        self.rule_entry.pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="重解析", command=self.reparse_chapters).pack(side=tk.LEFT, padx=3)

        ttk.Label(top, text="主题:").pack(side=tk.LEFT, padx=(14, 3))
        theme_box = ttk.Combobox(top, textvariable=self.theme_var, width=8, state="readonly")
        theme_box["values"] = ["warm", "green"]
        theme_box.pack(side=tk.LEFT)
        theme_box.bind("<<ComboboxSelected>>", lambda e: self.apply_theme(self.theme_var.get()))

        ttk.Label(top, text="字号:").pack(side=tk.LEFT, padx=(12, 3))
        font_spin = ttk.Spinbox(top, from_=12, to=40, width=4, textvariable=self.font_size_var, command=self.apply_text_style)
        font_spin.pack(side=tk.LEFT)

        ttk.Label(top, text="行距:").pack(side=tk.LEFT, padx=(8, 3))
        line_spin = ttk.Spinbox(top, from_=1.2, to=3.0, increment=0.1, width=4, textvariable=self.line_spacing_var, command=self.apply_text_style)
        line_spin.pack(side=tk.LEFT)

        main = ttk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        # 左侧目录面板
        self.sidebar_frame = ttk.Frame(main)
        self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.chapter_list = tk.Listbox(self.sidebar_frame, width=34, exportselection=False)
        self.chapter_list.pack(side=tk.LEFT, fill=tk.Y, expand=False)
        self.chapter_list.bind("<<ListboxSelect>>", self.on_chapter_select)

        left_scroll = ttk.Scrollbar(self.sidebar_frame, orient=tk.VERTICAL, command=self.chapter_list.yview)
        left_scroll.pack(side=tk.LEFT, fill=tk.Y)
        self.chapter_list.config(yscrollcommand=left_scroll.set)

        # 右侧阅读区
        right = ttk.Frame(main)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.text = tk.Text(right, wrap=tk.WORD, undo=True)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.text.bind("<<Modified>>", self.on_text_modified)
        self.text.bind("<MouseWheel>", self.on_scroll_event)
        self.text.bind("<Button-4>", self.on_scroll_event)  # Linux
        self.text.bind("<Button-5>", self.on_scroll_event)  # Linux
        self.text.bind("<KeyRelease>", lambda e: self.update_progress_debounced())

        txt_scroll = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.on_text_scrollbar)
        txt_scroll.pack(side=tk.LEFT, fill=tk.Y)
        self._text_scrollbar = txt_scroll
        self.text.config(yscrollcommand=self.on_text_yscroll)
        self.text.config(state=tk.DISABLED)

        bottom = ttk.Frame(self.root)
        bottom.pack(fill=tk.X, padx=8, pady=(0, 8))

        self.progress = ttk.Progressbar(bottom, orient=tk.HORIZONTAL, mode="determinate")
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        ttk.Label(bottom, textvariable=self.progress_text, width=24).pack(side=tk.LEFT)
        ttk.Label(bottom, textvariable=self.status_text).pack(side=tk.LEFT, padx=(10, 0))

    # -------------------- 主题与样式 --------------------
    def apply_theme(self, theme_name):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        if theme_name == "green":
            bg = "#e8f5e9"
            fg = "#1b5e20"
            text_bg = "#f1f8e9"
            text_fg = "#1f3b1f"
            select_bg = "#7aa57f"
        else:
            bg = "#f5ecd9"
            fg = "#4e3b2a"
            text_bg = "#fff9ee"
            text_fg = "#3b2e22"
            select_bg = "#b89c72"

        self.root.configure(bg=bg)
        style.configure(".", background=bg, foreground=fg)
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TButton", background=bg, foreground=fg)
        style.configure("TProgressbar", troughcolor="#d7c7a9", background="#8c6a43")

        self.text.configure(bg=text_bg, fg=text_fg, insertbackground=fg)
        self.chapter_list.configure(bg=text_bg, fg=text_fg, selectbackground=select_bg, selectforeground="#ffffff")

        self.apply_text_style()
        self.save_state()

    def apply_text_style(self):
        size = self.font_size_var.get()
        spacing = self.line_spacing_var.get()
        self.text.configure(font=("Microsoft YaHei UI", size))
        self.text.tag_configure("body", spacing1=2, spacing3=2, lmargin1=8, lmargin2=8)
        self.text.tag_configure("line", spacing2=int(size * (spacing - 1)))
        self.text.tag_add("body", "1.0", tk.END)
        self.text.tag_add("line", "1.0", tk.END)
        self.save_state()

    # -------------------- 打开/解码（大文件优化） --------------------
    def open_file(self):
        path = filedialog.askopenfilename(
            title="选择TXT文件",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not path:
            return
        if self.unsaved and not self.ask_save_before_continue():
            return

        self.current_file = path
        self.file_id = None
        self.raw_bytes = b""
        self.loaded_encoding = None
        self.lines = []
        self.chapters = []
        self.chapter_prefix_chars = []
        self.total_chars = 0
        self.current_chapter_idx = 0
        self.edited_chapter_text.clear()
        self.unsaved = False
        self.current_chapter_dirty = False
        self.encoding_var.set("auto")

        self.set_status("正在读取文件...")
        self.root.update_idletasks()

        try:
            with open(path, "rb") as f:
                self.raw_bytes = f.read()
        except Exception as e:
            messagebox.showerror("错误", f"读取文件失败:\n{e}")
            return

        self.file_id = self.make_file_id(path, self.raw_bytes)

        # 分帧加载，避免UI长时间“假死”
        if self._open_job is not None:
            self.root.after_cancel(self._open_job)
            self._open_job = None
        self._open_pipeline_step = 0
        self._open_job = self.root.after(10, self.open_pipeline)

    def open_pipeline(self):
        # 分多步执行：解码 -> 行切分 -> 章节解析 -> 列表渲染 -> 恢复进度 -> 展示章节
        try:
            if self._open_pipeline_step == 0:
                self.set_status("正在识别编码并解码...")
                self.root.update_idletasks()
                text, used_encoding = self.decode_bytes(self.raw_bytes, self.encoding_var.get())
                if text is None:
                    messagebox.showerror("错误", "无法识别文件编码，请手动选择编码。")
                    return
                self.loaded_encoding = used_encoding
                self._decoded_text = text.replace("\r\n", "\n").replace("\r", "\n")
                self._open_pipeline_step = 1
                self._open_job = self.root.after(1, self.open_pipeline)
                return

            if self._open_pipeline_step == 1:
                self.set_status("正在构建行缓存...")
                self.root.update_idletasks()
                self.lines = self._decoded_text.splitlines(keepends=True)
                if not self.lines:
                    self.lines = [""]
                del self._decoded_text
                self._open_pipeline_step = 2
                self._open_job = self.root.after(1, self.open_pipeline)
                return

            if self._open_pipeline_step == 2:
                self.set_status("正在解析章节...")
                self.root.update_idletasks()
                self.parse_chapters_from_lines()
                self._open_pipeline_step = 3
                self._open_job = self.root.after(1, self.open_pipeline)
                return

            if self._open_pipeline_step == 3:
                self.set_status("正在生成目录...")
                self.root.update_idletasks()
                self.render_chapter_list()
                self.restore_progress()
                self.show_chapter(self.current_chapter_idx, from_restore=True)
                self.unsaved = False
                self.update_title()
                self.set_status(f"已加载: {safe_basename(self.current_file)} | 编码: {self.loaded_encoding} | 章节: {len(self.chapters)}")
                self._open_job = None
                return
        finally:
            pass

    def decode_bytes(self, raw, selected):
        text = None
        used = None

        if selected != "auto":
            try:
                text = raw.decode(selected)
                used = selected
                return text, used
            except Exception as e:
                messagebox.showerror("解码失败", f"使用编码 {selected} 失败:\n{e}")
                return None, None

        candidates = []
        if chardet:
            try:
                guess = chardet.detect(raw).get("encoding")
                if guess:
                    candidates.append(guess.lower())
            except Exception:
                pass
        candidates.extend(["utf-8", "utf-8-sig", "gb18030", "gbk", "gb2312", "big5", "latin-1"])

        tried = set()
        for enc in candidates:
            if enc in tried:
                continue
            tried.add(enc)
            try:
                text = raw.decode(enc)
                used = enc
                break
            except Exception:
                continue
        return text, used

    def reload_with_selected_encoding(self):
        if not self.raw_bytes:
            return
        if self.unsaved:
            ok = messagebox.askyesno("提示", "当前有未保存修改，切换编码会丢失未保存编辑，继续吗？")
            if not ok:
                return
        self.edited_chapter_text.clear()
        self.unsaved = False
        self.current_chapter_dirty = False

        self.set_status("正在按新编码重载...")
        self.root.update_idletasks()
        text, used_encoding = self.decode_bytes(self.raw_bytes, self.encoding_var.get())
        if text is None:
            return
        self.loaded_encoding = used_encoding
        self.lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines(keepends=True)
        if not self.lines:
            self.lines = [""]
        self.parse_chapters_from_lines()
        self.render_chapter_list()
        self.current_chapter_idx = 0
        self.show_chapter(0)
        self.set_status(f"已按 {used_encoding} 重载")

    # -------------------- 章节解析（行号索引+精准进度基础） --------------------
    def parse_chapters_from_lines(self):
        rule = self.rule_var.get().strip() or DEFAULT_RULE
        try:
            regex = re.compile(rule, re.MULTILINE)
        except re.error as e:
            messagebox.showerror("章节规则错误", f"正则表达式无效:\n{e}")
            regex = re.compile(DEFAULT_RULE, re.MULTILINE)
            self.rule_var.set(DEFAULT_RULE)

        starts = []
        for i, line in enumerate(self.lines):
            s = line.strip()
            if s and regex.match(s):
                starts.append((s, i))

        if not starts:
            starts = [("正文", 0)]

        chapters = []
        for idx, (title, start_line) in enumerate(starts):
            end_line = starts[idx + 1][1] if idx + 1 < len(starts) else len(self.lines)
            char_len = sum(len(x) for x in self.lines[start_line:end_line])
            chapters.append({
                "title": title if title else f"章节{idx + 1}",
                "start_line": start_line,
                "end_line": end_line,
                "char_len": char_len
            })

        self.chapters = chapters

        # 构建前缀和用于精准全文进度
        self.chapter_prefix_chars = []
        acc = 0
        for ch in self.chapters:
            self.chapter_prefix_chars.append(acc)
            acc += ch["char_len"]
        self.total_chars = max(acc, 1)

        self.save_state()

    def reparse_chapters(self):
        if not self.lines:
            return
        if self.unsaved:
            ok = messagebox.askyesno("提示", "当前有未保存修改，重解析可能改变章节定位，继续吗？")
            if not ok:
                return
        idx = self.current_chapter_idx
        self.parse_chapters_from_lines()
        self.render_chapter_list()
        self.current_chapter_idx = min(idx, len(self.chapters) - 1)
        self.show_chapter(self.current_chapter_idx)
        self.set_status(f"重解析完成，章节数: {len(self.chapters)}")

    def render_chapter_list(self):
        self.chapter_list.delete(0, tk.END)
        for i, ch in enumerate(self.chapters):
            title = ch["title"].replace("\n", " ").strip()
            self.chapter_list.insert(tk.END, f"{i + 1:04d}  {title[:46]}")

    def get_chapter_text(self, idx):
        if idx in self.edited_chapter_text:
            return self.edited_chapter_text[idx]
        ch = self.chapters[idx]
        return "".join(self.lines[ch["start_line"]:ch["end_line"]])

    def on_chapter_select(self, _event=None):
        if self.is_updating_ui:
            return
        if not self.chapter_list.curselection():
            return
        idx = self.chapter_list.curselection()[0]
        self.show_chapter(idx)

    def show_chapter(self, idx, from_restore=False):
        if not self.chapters:
            return
        idx = max(0, min(idx, len(self.chapters) - 1))

        if not from_restore:
            self.flush_current_chapter_edit_to_cache()

        self.current_chapter_idx = idx
        content = self.get_chapter_text(idx)

        self.is_updating_ui = True
        try:
            self.text.config(state=tk.NORMAL)
            self.text.delete("1.0", tk.END)
            self.text.insert("1.0", content)
            if not self.is_edit_mode:
                self.text.config(state=tk.DISABLED)

            self.apply_text_style()

            self.chapter_list.selection_clear(0, tk.END)
            self.chapter_list.selection_set(idx)
            self.chapter_list.see(idx)
        finally:
            self.is_updating_ui = False

        self.update_progress()
        self.save_progress()
        self.update_title()

    # -------------------- 编辑/保存（稳态：只在保存时合并） --------------------
    def toggle_edit(self):
        if not self.chapters:
            return
        self.is_edit_mode = not self.is_edit_mode
        self.text.config(state=tk.NORMAL if self.is_edit_mode else tk.DISABLED)
        self.set_status("编辑模式已开启" if self.is_edit_mode else "编辑模式已关闭")

    def on_text_modified(self, _event=None):
        if self.is_updating_ui:
            self.text.edit_modified(False)
            return
        if not self.is_edit_mode:
            self.text.edit_modified(False)
            return
        if self.text.edit_modified():
            self.current_chapter_dirty = True
            self.unsaved = True
            self.update_title()
            self.text.edit_modified(False)
            self.update_progress_debounced()

    def flush_current_chapter_edit_to_cache(self):
        if not self.chapters or not self.current_chapter_dirty:
            return
        if not self.is_edit_mode:
            return
        content = self.text.get("1.0", "end-1c")
        self.edited_chapter_text[self.current_chapter_idx] = content
        self.current_chapter_dirty = False
        self.unsaved = True

    def build_final_text_for_save(self):
        # 将编辑过章节批量回写到新 lines，最后一次性合并，避免反复重排大字符串
        self.flush_current_chapter_edit_to_cache()

        if not self.edited_chapter_text:
            return "".join(self.lines)

        new_lines = list(self.lines)
        # 逆序替换行区间，避免前面替换影响后续章节行号
        changed = sorted(self.edited_chapter_text.items(), key=lambda x: x[0], reverse=True)
        for idx, chapter_text in changed:
            if idx < 0 or idx >= len(self.chapters):
                continue
            ch = self.chapters[idx]
            replacement = chapter_text.splitlines(keepends=True)
            if chapter_text and not chapter_text.endswith("\n"):
                # 保持编辑原样，不强制补换行
                pass
            new_lines[ch["start_line"]:ch["end_line"]] = replacement

        return "".join(new_lines)

    def save_file(self):
        if not self.current_file:
            self.save_as()
            return

        if not self.unsaved:
            self.set_status("没有未保存修改")
            return

        text_to_save = self.build_final_text_for_save()
        enc = self.encoding_var.get()
        if enc == "auto":
            enc = self.loaded_encoding or "utf-8"

        try:
            with open(self.current_file, "wb") as f:
                f.write(text_to_save.encode(enc, errors="replace"))
        except Exception as e:
            messagebox.showerror("保存失败", str(e))
            return

        # 保存成功后，重建内存结构，确保索引与磁盘一致
        self.raw_bytes = text_to_save.encode(enc, errors="replace")
        self.lines = text_to_save.splitlines(keepends=True)
        if not self.lines:
            self.lines = [""]
        self.edited_chapter_text.clear()
        self.current_chapter_dirty = False
        self.unsaved = False
        self.loaded_encoding = enc

        old_idx = self.current_chapter_idx
        self.parse_chapters_from_lines()
        self.render_chapter_list()
        self.current_chapter_idx = min(old_idx, len(self.chapters) - 1)
        self.show_chapter(self.current_chapter_idx)
        self.update_title()
        self.set_status("已保存到原文件")

    def save_as(self):
        if not self.lines and not self.edited_chapter_text:
            messagebox.showinfo("提示", "请先打开文件")
            return
        path = filedialog.asksaveasfilename(
            title="另存为",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not path:
            return

        text_to_save = self.build_final_text_for_save()
        enc = self.encoding_var.get()
        if enc == "auto":
            enc = self.loaded_encoding or "utf-8"

        try:
            with open(path, "wb") as f:
                f.write(text_to_save.encode(enc, errors="replace"))
        except Exception as e:
            messagebox.showerror("保存失败", str(e))
            return

        # 另存为后切换到新文件上下文
        self.current_file = path
        self.raw_bytes = text_to_save.encode(enc, errors="replace")
        self.lines = text_to_save.splitlines(keepends=True)
        if not self.lines:
            self.lines = [""]
        self.file_id = self.make_file_id(path, self.raw_bytes)
        self.loaded_encoding = enc
        self.edited_chapter_text.clear()
        self.current_chapter_dirty = False
        self.unsaved = False

        old_idx = self.current_chapter_idx
        self.parse_chapters_from_lines()
        self.render_chapter_list()
        self.current_chapter_idx = min(old_idx, len(self.chapters) - 1)
        self.show_chapter(self.current_chapter_idx)
        self.update_title()
        self.set_status(f"已另存为: {safe_basename(path)}")

    # -------------------- 精准进度 --------------------
    def on_text_scrollbar(self, *args):
        self.text.yview(*args)
        self.update_progress_debounced()

    def on_text_yscroll(self, a, b):
        self._text_scrollbar.set(a, b)
        self.update_progress_debounced()

    def on_scroll_event(self, _event=None):
        self.update_progress_debounced()

    def update_progress_debounced(self):
        if self._progress_job is not None:
            self.root.after_cancel(self._progress_job)
        self._progress_job = self.root.after(80, self.update_progress)

    def update_progress(self):
        self._progress_job = None
        if not self.chapters:
            self.progress["value"] = 0
            self.progress_text.set("全文 0.0% | 本章 0.0%")
            return

        idx = self.current_chapter_idx
        idx = max(0, min(idx, len(self.chapters) - 1))
        ch = self.chapters[idx]

        y_first, _ = self.text.yview()
        y_first = max(0.0, min(1.0, y_first))

        chapter_char_len = max(ch["char_len"], 1)
        chapter_pos = int(chapter_char_len * y_first)
        global_pos = self.chapter_prefix_chars[idx] + chapter_pos

        global_ratio = min(1.0, max(0.0, global_pos / self.total_chars))
        chapter_ratio = y_first

        self.progress["value"] = global_ratio * 100.0
        self.progress_text.set(f"全文 {global_ratio * 100:.1f}% | 本章 {chapter_ratio * 100:.1f}%")

        self.save_progress()

    # -------------------- 进度记忆 --------------------
    def save_progress(self):
        if not self.file_id:
            return
        y_first, _ = self.text.yview()
        self.state.setdefault("files", {})[self.file_id] = {
            "path": self.current_file,
            "chapter_idx": self.current_chapter_idx,
            "yview": y_first,
            "encoding": self.encoding_var.get() if self.encoding_var.get() != "auto" else (self.loaded_encoding or "auto"),
        }
        self.save_state()

    def restore_progress(self):
        info = self.state.get("files", {}).get(self.file_id)
        self.current_chapter_idx = 0
        if not info:
            return

        self.current_chapter_idx = min(max(0, info.get("chapter_idx", 0)), max(0, len(self.chapters) - 1))
        enc = info.get("encoding", "auto")
        if enc in ["auto"] + ENCODINGS:
            self.encoding_var.set(enc)

        # 章节展示后再恢复 yview
        self.root.after(10, lambda: self.restore_yview(info.get("yview", 0.0)))

    def restore_yview(self, y):
        try:
            y = float(y)
        except Exception:
            y = 0.0
        y = max(0.0, min(1.0, y))
        self.text.yview_moveto(y)
        self.update_progress()

    # -------------------- 导航/快捷键 --------------------
    def bind_hotkeys(self):
        self.root.bind("<Prior>", lambda e: self.page_up())       # PageUp
        self.root.bind("<Next>", lambda e: self.page_down())      # PageDown
        self.root.bind("<Left>", lambda e: self.prev_chapter())   # 左
        self.root.bind("<Right>", lambda e: self.next_chapter())  # 右
        self.root.bind("<KeyPress-e>", lambda e: self.toggle_edit())
        self.root.bind("<Control-s>", lambda e: self.save_file())
        self.root.bind("<Command-s>", lambda e: self.save_file())  # macOS

    def page_up(self):
        self.text.yview_scroll(-1, "page")
        self.update_progress()

    def page_down(self):
        self.text.yview_scroll(1, "page")
        self.update_progress()

    def prev_chapter(self):
        self.show_chapter(self.current_chapter_idx - 1)

    def next_chapter(self):
        self.show_chapter(self.current_chapter_idx + 1)

    # -------------------- 目录显隐（按钮固定可见） --------------------
    def toggle_sidebar(self):
        if self.sidebar_visible:
            self.sidebar_frame.pack_forget()
            self.sidebar_visible = False
            self.sidebar_btn.configure(text="目录 ▶")
        else:
            self.sidebar_frame.pack(side=tk.LEFT, fill=tk.Y, before=self.text.master)
            self.sidebar_visible = True
            self.sidebar_btn.configure(text="目录 ◀")

    # -------------------- 通用 --------------------
    def set_status(self, msg):
        self.status_text.set(msg)

    def make_file_id(self, path, content):
        # 取前 128KB + 文件大小做标识，速度和稳定性平衡
        h = hashlib.md5(content[:1024 * 128] + str(len(content)).encode("utf-8")).hexdigest()
        return f"{os.path.abspath(path)}::{h}"

    def update_title(self):
        name = safe_basename(self.current_file) if self.current_file else "未打开文件"
        mark = "*" if self.unsaved else ""
        self.root.title(f"{APP_NAME} - {mark}{name}")

    def ask_save_before_continue(self):
        if not self.unsaved:
            return True
        result = messagebox.askyesnocancel(
            "未保存修改",
            "当前有未保存修改，是否先保存？\n是=保存并继续，否=不保存继续，取消=中止操作"
        )
        if result is None:
            return False
        if result is True:
            self.save_file()
            return not self.unsaved
        return True

    def on_close(self):
        if not self.ask_save_before_continue():
            return
        self.save_state()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ReaderApp(root)
    root.mainloop()
