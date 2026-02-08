import os, re, json, threading, time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import sys

try:
    import chardet
except ImportError:
    chardet = None

APP_NAME = "极速阅读器 Pro v4.0.1"

# ... (FastTextIndexer 类保持不变) ...
class FastTextIndexer:
    def __init__(self, task_id, file_path, encoding, rule):
        self.task_id = task_id
        self.file_path = file_path
        self.encoding = encoding
        self.rule = re.compile(rule.encode(encoding, errors='ignore'))
        self.is_running = True

    def scan(self, callback):
        chapters = []
        total_chars, total_han = 0, 0
        try:
            with open(self.file_path, 'rb') as f:
                chapters.append(("正文开始", 0))
                line_count = 0
                while self.is_running:
                    pos = f.tell()
                    line = f.readline()
                    if not line: break
                    try:
                        if self.rule.match(line):
                            title = line.decode(self.encoding, errors='ignore').strip()
                            chapters.append((title, pos))
                        decoded = line.decode(self.encoding, errors='ignore')
                        total_chars += len(decoded)
                        if any('\u4e00' <= c <= '\u9fff' for c in decoded):
                            total_han += len(re.findall(r'[\u4e00-\u9fff]', decoded))
                    except: pass
                    line_count += 1
                    if line_count % 8000 == 0:
                        if not self.is_running: return
                        callback(self.task_id, list(chapters), total_chars, total_han, False)
                if self.is_running:
                    callback(self.task_id, chapters, total_chars, total_han, True)
        except Exception as e: print(f"Indexer Error: {e}")

class ReaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1250x850")
        
        self.current_file = None
        self.file_bytes = b""
        self.encoding = "utf-8"
        self.chapters = []
        self.current_ch_idx = 0
        self.current_task_id = 0
        self.is_indexing = False
        self.is_editing = False
        self.last_reported_ch_count = 0 
        
        self.session_start_time = time.time()
        self.book_start_time = time.time()
        
        self.settings = self.load_settings()
        self.font_size = tk.IntVar(value=self.settings.get("font_size", 18))
        self.line_spacing = tk.DoubleVar(value=self.settings.get("line_spacing", 1.6))
        self.theme = tk.StringVar(value=self.settings.get("theme", "warm"))
        self.chapter_rule = tk.StringVar(value=self.settings.get("rule", r"^(第[〇零一二三四五六七八九十百千万0-9]+[章节回卷篇].*)"))
        
        self.status_var = tk.StringVar(value="准备就绪")
        self.stats_var = tk.StringVar()
        self.ch_stats_var = tk.StringVar()
        self.progress_var = tk.StringVar()
        self.timer_var = tk.StringVar(value="计时初始化...")

        self._setup_ui()
        self.apply_theme()
        self._update_timer_loop()
        
        last_file = self.settings.get("last_file")
        if last_file and os.path.exists(last_file):
            self.root.after(200, lambda: self.open_file(last_file))

    def load_settings(self):
        try:
            cfg_path = os.path.join(os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__), "reader_settings.json")
            if os.path.exists(cfg_path):
                with open(cfg_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except: pass
        return {"files": {}, "global_total_time": 0}

    def save_settings(self):
        if not self.current_file or self.is_indexing: return
        
        now = time.time()
        elapsed = int(now - self.book_start_time)
        self.book_start_time = now
        
        if "files" not in self.settings: self.settings["files"] = {}
        book_cfg = self.settings["files"].get(self.current_file, {})
        total_book_time = book_cfg.get("total_time", 0) + elapsed
        
        try: scroll_pos = self.text.yview()[0]
        except: scroll_pos = 0.0
        
        # 增加安全检查：确保当前索引在 chapters 范围内
        if self.current_ch_idx < len(self.chapters):
            byte_pos = self.chapters[self.current_ch_idx][1]
        else:
            byte_pos = book_cfg.get("byte_pos", 0)
        
        self.settings["files"][self.current_file] = {
            "ch_idx": self.current_ch_idx, "byte_pos": byte_pos, 
            "offset": scroll_pos, "total_time": total_book_time
        }
        self.settings.update({
            "font_size": self.font_size.get(), "line_spacing": self.line_spacing.get(),
            "theme": self.theme.get(), "rule": self.chapter_rule.get(), "last_file": self.current_file
        })
        
        try:
            cfg_path = os.path.join(os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__), "reader_settings.json")
            with open(cfg_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except: pass

    def _setup_ui(self):
        bottom = tk.Frame(self.root, height=35, bg="#222")
        bottom.pack(side=tk.BOTTOM, fill=tk.X)
        bottom.pack_propagate(False)
        self.status_lbl = tk.Label(bottom, textvariable=self.status_var, fg="#00ff00", bg="#222", font=("Arial", 9, "bold"))
        self.status_lbl.pack(side=tk.LEFT, padx=10)
        tk.Label(bottom, textvariable=self.stats_var, fg="#999", bg="#222", font=("Arial", 9)).pack(side=tk.RIGHT, padx=10)
        tk.Label(bottom, textvariable=self.timer_var, fg="#f39c12", bg="#222", font=("Arial", 9, "bold")).pack(side=tk.RIGHT, padx=10)
        tk.Label(bottom, textvariable=self.ch_stats_var, fg="#3498db", bg="#222", font=("Arial", 9, "bold")).pack(side=tk.RIGHT, padx=10)
        tk.Label(bottom, textvariable=self.progress_var, fg="#999", bg="#222", font=("Arial", 9)).pack(side=tk.RIGHT, padx=10)

        toolbar = ttk.Frame(self.root, padding=5)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(toolbar, text="📂 打开", command=self.open_file_dialog).pack(side=tk.LEFT, padx=2)
        self.edit_btn = ttk.Button(toolbar, text="📝 编辑 (E)", command=self.toggle_edit_mode)
        self.edit_btn.pack(side=tk.LEFT, padx=2)
        self.save_btn = ttk.Button(toolbar, text="💾 保存 (Ctrl+S)", command=self.save_to_file, state=tk.DISABLED)
        self.save_btn.pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Label(toolbar, text="字号:").pack(side=tk.LEFT)
        ttk.Spinbox(toolbar, from_=10, to=60, width=3, textvariable=self.font_size, command=self.update_view_style).pack(side=tk.LEFT, padx=2)
        ttk.Label(toolbar, text="间距:").pack(side=tk.LEFT)
        ttk.Spinbox(toolbar, from_=1.0, to=3.0, increment=0.1, width=3, textvariable=self.line_spacing, command=self.update_view_style).pack(side=tk.LEFT, padx=2)
        ttk.Combobox(toolbar, textvariable=self.theme, values=["warm", "green", "dark", "paper"], width=6, state="readonly").pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        ttk.Label(toolbar, text="正则:").pack(side=tk.LEFT)
        reg_entry = ttk.Entry(toolbar, textvariable=self.chapter_rule)
        reg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(toolbar, text="解析", command=self.re_index).pack(side=tk.LEFT, padx=2)

        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        left_frame = tk.Frame(paned)
        tk.Button(left_frame, text="🎯 定位当前章节", font=("Arial", 9), relief=tk.FLAT, bg="#ddd", command=self.locate_current_chapter).pack(fill=tk.X)
        self.dir_list = tk.Listbox(left_frame, width=25, font=("Microsoft YaHei", 10), borderwidth=0, selectbackground="#3498db")
        self.dir_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.dir_list.bind("<<ListboxSelect>>", self.on_chapter_click)
        dir_scroll = ttk.Scrollbar(left_frame, command=self.dir_list.yview)
        dir_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.dir_list.config(yscrollcommand=dir_scroll.set)
        paned.add(left_frame, weight=1)
        text_frame = tk.Frame(paned)
        self.text = tk.Text(text_frame, wrap=tk.WORD, borderwidth=0, highlightthickness=2, padx=30, pady=20, undo=True)
        self.main_scroll = ttk.Scrollbar(text_frame, command=self.text.yview)
        self.main_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.text.config(yscrollcommand=self.main_scroll.set, state=tk.DISABLED)
        paned.add(text_frame, weight=4)

        self.root.bind("<KeyPress-Left>", lambda e: self.change_chapter(-1))
        self.root.bind("<KeyPress-Right>", lambda e: self.change_chapter(1))
        self.root.bind("e", lambda e: self.toggle_edit_mode())
        self.root.bind("E", lambda e: self.toggle_edit_mode())
        self.root.bind("<Control-s>", lambda e: self.save_to_file())

    def _update_timer_loop(self):
        now = time.time()
        session_elapsed = int(now - self.session_start_time)
        book_history = 0
        if self.current_file:
            book_history = self.settings.get("files", {}).get(self.current_file, {}).get("total_time", 0)
        book_total = book_history + int(now - self.book_start_time)
        self.timer_var.set(f"本场: {session_elapsed//60}分 | 本书: {book_total//60}分")
        self.root.after(10000, self._update_timer_loop)

    def open_file_dialog(self):
        p = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if p: self.open_file(p)

    def open_file(self, path):
        if self.is_editing and self.text.edit_modified():
            if not messagebox.askyesno("提醒", "当前章节已修改，是否放弃更改？"): return
        self.save_settings() 
        self.current_file = path
        self.book_start_time = time.time() 
        with open(path, 'rb') as f: self.file_bytes = f.read()
        self.encoding = self.detect_encoding(self.file_bytes[:30000])
        file_info = self.settings.get("files", {}).get(path, {})
        self.current_ch_idx = file_info.get("ch_idx", 0)
        self.dir_list.delete(0, tk.END)
        self.last_reported_ch_count = 0
        self.chapters = [("解析中...", file_info.get("byte_pos", 0))]
        self.load_chapter_content(self.current_ch_idx, force_pos=file_info.get("byte_pos", 0))
        self.re_index()
        offset = file_info.get("offset", 0.0)
        self.root.after(300, lambda: self.text.yview_moveto(offset))

    def detect_encoding(self, chunk):
        if chardet:
            res = chardet.detect(chunk)
            if res['confidence'] > 0.6: return res['encoding']
        for enc in ['utf-8', 'gbk', 'gb18030']:
            try: chunk.decode(enc); return enc
            except: pass
        return 'utf-8'

    def re_index(self):
        if not self.current_file: return
        self.is_indexing = True
        self.save_btn.config(state=tk.DISABLED) 
        self.current_task_id += 1
        indexer = FastTextIndexer(self.current_task_id, self.current_file, self.encoding, self.chapter_rule.get())
        threading.Thread(target=indexer.scan, args=(self.update_ui_callback,), daemon=True).start()

    def update_ui_callback(self, task_id, chapters, total_c, total_h, is_done):
        if task_id != self.current_task_id: return
        self.root.after(0, lambda: self._sync_ui(task_id, chapters, total_c, total_h, is_done))

    def _sync_ui(self, task_id, chapters, total_c, total_h, is_done):
        if task_id != self.current_task_id: return
        self.chapters = chapters
        current_count = len(chapters)
        if current_count > self.last_reported_ch_count:
            for i in range(self.last_reported_ch_count, current_count):
                self.dir_list.insert(tk.END, f" {chapters[i][0]}")
            self.last_reported_ch_count = current_count
        
        if is_done:
            self.is_indexing = False
            if self.is_editing: self.save_btn.config(state=tk.NORMAL)
            self.stats_var.set(f"全书: {total_c:,}字 | 汉字: {total_h:,}")
            self.status_var.set(os.path.basename(self.current_file))
            self.dir_list.selection_clear(0, tk.END)
            if self.current_ch_idx < len(self.chapters):
                self.dir_list.selection_set(self.current_ch_idx)
            self.update_progress_label()
            self.refresh_chapter_stats()
        else:
            self.stats_var.set(f"索引中: {total_c//10000}万字...")

    def load_chapter_content(self, idx, force_pos=None):
        """修复：增加边界检查，防止 IndexError"""
        if not self.file_bytes: return
        # --- 核心修复：边界检查 ---
        if idx < 0 or idx >= len(self.chapters):
            print(f"DEBUG: Index {idx} out of range (chapters len: {len(self.chapters)})")
            return 
            
        if self.is_editing and self.text.edit_modified():
            if not messagebox.askyesno("保存确认", "本章节有未保存的修改，是否放弃？"): return
            
        start = force_pos if force_pos is not None else self.chapters[idx][1]
        if idx + 1 < len(self.chapters):
            end = self.chapters[idx+1][1]
        else:
            end = len(self.file_bytes)
            
        try:
            content = self.file_bytes[start:end].decode(self.encoding, errors='ignore').replace('\r\n', '\n')
            self.text.config(state=tk.NORMAL)
            self.text.delete("1.0", tk.END)
            self.text.insert("1.0", content)
            self.text.edit_modified(False)
            if not self.is_editing: self.text.config(state=tk.DISABLED)
            if force_pos is None: self.current_ch_idx = idx
            self.update_progress_label()
            self.refresh_chapter_stats()
            self.update_view_style()
        except Exception as e: print(f"Load Error: {e}")

    def refresh_chapter_stats(self):
        content = self.text.get("1.0", tk.END).strip()
        self.ch_stats_var.set(f"本章: {len(content):,}字")

    def toggle_edit_mode(self):
        if not self.current_file: return
        self.is_editing = not self.is_editing
        if self.is_editing:
            self.text.config(state=tk.NORMAL, highlightbackground="#3498db")
            self.edit_btn.config(text="📖 退出编辑")
            if not self.is_indexing: self.save_btn.config(state=tk.NORMAL)
            self.status_var.set("编辑模式 - 翻页已禁用")
            self.status_lbl.config(fg="#3498db")
        else:
            if self.text.edit_modified():
                if messagebox.askyesno("保存", "内容已修改，退出前是否保存？"): self.save_to_file()
            self.text.config(state=tk.DISABLED, highlightbackground="#ddd")
            self.edit_btn.config(text="📝 编辑 (E)")
            self.save_btn.config(state=tk.DISABLED)
            self.status_var.set(os.path.basename(self.current_file))
            self.status_lbl.config(fg="#00ff00")

    def save_to_file(self):
        if not self.current_file or not self.is_editing or self.is_indexing: return
        try:
            new_content = self.text.get("1.0", tk.END).strip() + "\n\n"
            new_bytes = new_content.encode(self.encoding, errors='ignore')
            start = self.chapters[self.current_ch_idx][1]
            end = self.chapters[self.current_ch_idx+1][1] if self.current_ch_idx + 1 < len(self.chapters) else len(self.file_bytes)
            full_data = self.file_bytes[:start] + new_bytes + self.file_bytes[end:]
            with open(self.current_file, 'wb') as f: f.write(full_data)
            self.file_bytes = full_data
            self.text.edit_modified(False)
            messagebox.showinfo("成功", "章节已保存，正在刷新索引...")
            self.re_index() 
        except Exception as e: messagebox.showerror("保存失败", f"错误详情: {e}")

    def update_progress_label(self):
        if not self.chapters or self.is_indexing:
            self.progress_var.set("进度: 计算中...")
            return
        total = len(self.chapters)
        p = (self.current_ch_idx + 1) / total * 100
        self.progress_var.set(f"进度: {p:.1f}% ({self.current_ch_idx+1}/{total}章)")

    def change_chapter(self, delta):
        if self.is_editing: return
        new_idx = self.current_ch_idx + delta
        # 增加安全范围检查
        if 0 <= new_idx < len(self.chapters):
            self.load_chapter_content(new_idx)
            self.dir_list.selection_clear(0, tk.END)
            self.dir_list.selection_set(new_idx)
            self.dir_list.see(new_idx)
            self.save_settings()

    def on_chapter_click(self, e):
        sel = self.dir_list.curselection()
        # 增加 sel 合法性检查
        if sel and sel[0] < len(self.chapters): 
            self.load_chapter_content(sel[0])
            self.save_settings()

    def locate_current_chapter(self):
        if self.chapters and self.current_ch_idx < len(self.chapters):
            self.dir_list.selection_clear(0, tk.END)
            self.dir_list.selection_set(self.current_ch_idx)
            self.dir_list.see(self.current_ch_idx)

    def update_view_style(self, _=None):
        f_size = self.font_size.get()
        s_val = int(f_size * (self.line_spacing.get() - 1))
        self.text.configure(font=("Microsoft YaHei", f_size), spacing2=s_val, spacing1=4, spacing3=4)

    def apply_theme(self):
        themes = {
            "warm": {"bg": "#f4f0e6", "fg": "#332c22", "l_bg": "#ede7da"},
            "green": {"bg": "#e8f5e9", "fg": "#1b5e20", "l_bg": "#dcedc8"},
            "dark": {"bg": "#1a1a1a", "fg": "#bbb", "l_bg": "#252525"},
            "paper": {"bg": "#fafafa", "fg": "#111", "l_bg": "#eee"}
        }
        t = themes.get(self.theme.get(), themes["warm"])
        self.text.configure(bg=t["bg"], fg=t["fg"], insertbackground=t["fg"])
        self.dir_list.configure(bg=t["l_bg"], fg=t["fg"], selectbackground="#3498db")
        self.update_view_style()

    def on_close(self):
        if self.is_editing and self.text.edit_modified():
            if not messagebox.askyesno("确认退出", "有未保存的修改，确定退出吗？"): return
        try: self.save_settings()
        except: pass
        finally: self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    app = ReaderApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
