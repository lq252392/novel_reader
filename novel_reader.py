import os, re, json, threading, time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import sys

try:
    import chardet
except ImportError:
    chardet = None

APP_NAME = "极速阅读器 Pro v3.7"


def get_config_file():
    """获取配置文件路径，支持打包后的exe文件，保存在EXE所在目录"""
    if getattr(sys, 'frozen', False):
        # 如果是打包后的可执行文件，返回EXE所在目录
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, "reader_settings.json")
    else:
        # 如果是开发环境中的Python脚本
        return os.path.join(os.path.dirname(__file__), "reader_settings.json")

CONFIG_FILE = get_config_file()

class FastTextIndexer:
    """高性能索引器：精确统计 + 增量反馈"""
    def __init__(self, task_id, file_path, encoding, rule):
        self.task_id = task_id
        self.file_path = file_path
        self.encoding = encoding
        self.rule = re.compile(rule.encode(encoding, errors='ignore'))
        self.is_running = True

    def scan(self, callback):
        chapters = []
        total_chars = 0
        total_han = 0
        try:
            with open(self.file_path, 'rb') as f:
                chapters.append(("正文开始", 0))
                line_count = 0
                while self.is_running:
                    pos = f.tell()
                    line = f.readline()
                    if not line: break
                    
                    try:
                        # 1. 章节匹配
                        if self.rule.match(line):
                            title = line.decode(self.encoding, errors='ignore').strip()
                            chapters.append((title, pos))
                        
                        # 2. 精确字数统计 (不再采样)
                        decoded = line.decode(self.encoding, errors='ignore')
                        total_chars += len(decoded)
                        if any('\u4e00' <= c <= '\u9fff' for c in decoded):
                            total_han += len(re.findall(r'[\u4e00-\u9fff]', decoded))
                    except: pass
                    
                    line_count += 1
                    # 降低汇报频率，每5000行汇报一次，保证扫描性能
                    if line_count % 5000 == 0:
                        if not self.is_running: return
                        callback(self.task_id, list(chapters), total_chars, total_han, False)
                
                if self.is_running:
                    callback(self.task_id, chapters, total_chars, total_han, True)
        except Exception as e:
            print(f"Indexer Error: {e}")

class ReaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1200x850")
        
        self.current_file = None
        self.file_bytes = b""
        self.encoding = "utf-8"
        self.chapters = []
        self.current_ch_idx = 0
        self.current_task_id = 0
        self.last_reported_ch_count = 0 # 用于增量更新目录
        
        self.settings = self.load_settings()
        self.font_size = tk.IntVar(value=self.settings.get("font_size", 18))
        self.line_spacing = tk.DoubleVar(value=self.settings.get("line_spacing", 1.6))
        self.theme = tk.StringVar(value=self.settings.get("theme", "warm"))
        self.chapter_rule = tk.StringVar(value=self.settings.get("rule", r"^(第[〇零一二三四五六七八九十百千万0-9]+[章节回卷篇].*)"))
        
        self.status_var = tk.StringVar(value="就绪")
        self.stats_var = tk.StringVar()
        self.ch_stats_var = tk.StringVar()
        self.progress_var = tk.StringVar()

        self._setup_ui()
        self.apply_theme()
        
        last_file = self.settings.get("last_file")
        if last_file and os.path.exists(last_file):
            self.root.after(200, lambda: self.open_file(last_file))

    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        return {}

    def save_settings(self):
        if not self.current_file: return
        self.settings.update({
            "font_size": self.font_size.get(),
            "line_spacing": self.line_spacing.get(),
            "theme": self.theme.get(),
            "rule": self.chapter_rule.get(),
            "last_file": self.current_file
        })
        if "files" not in self.settings: self.settings["files"] = {}
        
        try: scroll_pos = self.text.yview()[0]
        except: scroll_pos = 0.0
            
        byte_pos = self.chapters[self.current_ch_idx][1] if self.current_ch_idx < len(self.chapters) else 0
        self.settings["files"][self.current_file] = {
            "ch_idx": self.current_ch_idx, "byte_pos": byte_pos, "offset": scroll_pos
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, ensure_ascii=False, indent=2)

    def _setup_ui(self):
        # 底部栏
        bottom = tk.Frame(self.root, height=35, bg="#222")
        bottom.pack(side=tk.BOTTOM, fill=tk.X)
        bottom.pack_propagate(False)
        tk.Label(bottom, textvariable=self.status_var, fg="#00ff00", bg="#222", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=10)
        tk.Label(bottom, textvariable=self.stats_var, fg="#aaa", bg="#222", font=("Arial", 9)).pack(side=tk.RIGHT, padx=10)
        tk.Label(bottom, textvariable=self.ch_stats_var, fg="#aaa", bg="#222", font=("Arial", 9)).pack(side=tk.RIGHT, padx=10)
        tk.Label(bottom, textvariable=self.progress_var, fg="#aaa", bg="#222", font=("Arial", 9)).pack(side=tk.RIGHT, padx=10)

        # 顶部工具栏
        toolbar = ttk.Frame(self.root, padding=5)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(toolbar, text="📂 打开文件", command=self.open_file_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Label(toolbar, text="字号:").pack(side=tk.LEFT)
        ttk.Spinbox(toolbar, from_=10, to=60, width=4, textvariable=self.font_size, command=self.update_view_style).pack(side=tk.LEFT, padx=2)
        ttk.Label(toolbar, text="行距:").pack(side=tk.LEFT, padx=(5,0))
        ttk.Spinbox(toolbar, from_=1.0, to=3.5, increment=0.1, width=4, textvariable=self.line_spacing, command=self.update_view_style).pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Combobox(toolbar, textvariable=self.theme, values=["warm", "green", "dark", "paper"], width=8, state="readonly").pack(side=tk.LEFT, padx=2)
        self.root.bind("<<ComboboxSelected>>", lambda e: self.apply_theme())
        ttk.Entry(toolbar, textvariable=self.chapter_rule, width=15).pack(side=tk.LEFT, padx=10)
        ttk.Button(toolbar, text="解析", command=self.re_index).pack(side=tk.LEFT)

        # 主体
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # 目录区
        left_frame = tk.Frame(paned)
        # 定位按钮：放在目录最上方
        btn_box = tk.Frame(left_frame, bg="#ddd")
        btn_box.pack(side=tk.TOP, fill=tk.X)
        tk.Button(btn_box, text="🎯 定位当前章节", font=("Arial", 9), relief=tk.FLAT, bg="#ddd", command=self.locate_current_chapter).pack(fill=tk.X)
        
        self.dir_list = tk.Listbox(left_frame, width=28, font=("Microsoft YaHei", 10), borderwidth=0, activestyle='none')
        self.dir_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.dir_list.bind("<<ListboxSelect>>", self.on_chapter_click)
        dir_scroll = ttk.Scrollbar(left_frame, command=self.dir_list.yview)
        dir_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.dir_list.config(yscrollcommand=dir_scroll.set)
        paned.add(left_frame, weight=1)

        # 文本区
        text_frame = tk.Frame(paned)
        self.text = tk.Text(text_frame, wrap=tk.WORD, borderwidth=0, highlightthickness=0, padx=30, pady=20)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        main_scroll = ttk.Scrollbar(text_frame, command=self.text.yview)
        main_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.config(yscrollcommand=main_scroll.set)
        paned.add(text_frame, weight=4)

        self.root.bind("<KeyPress-Left>", lambda e: self.change_chapter(-1))
        self.root.bind("<KeyPress-Right>", lambda e: self.change_chapter(1))

    def open_file_dialog(self):
        p = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if p: self.open_file(p)

    def open_file(self, path):
        self.save_settings()
        self.current_task_id += 1 
        self.last_reported_ch_count = 0
        self.dir_list.delete(0, tk.END)
        
        self.current_file = path
        with open(path, 'rb') as f:
            self.file_bytes = f.read()
        
        self.encoding = self.detect_encoding(self.file_bytes[:30000])
        file_info = self.settings.get("files", {}).get(path, {})
        saved_byte_pos = file_info.get("byte_pos", 0)
        self.current_ch_idx = file_info.get("ch_idx", 0)
        
        self.chapters = [("正文加载中...", saved_byte_pos)]
        self.load_chapter_content(0, force_pos=saved_byte_pos)
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
        self.current_task_id += 1
        indexer = FastTextIndexer(self.current_task_id, self.current_file, self.encoding, self.chapter_rule.get())
        threading.Thread(target=indexer.scan, args=(self.update_ui_callback,), daemon=True).start()

    def update_ui_callback(self, task_id, chapters, total_c, total_h, is_done):
        if task_id != self.current_task_id: return
        self.root.after(0, lambda: self._sync_ui(task_id, chapters, total_c, total_h, is_done))

    def _sync_ui(self, task_id, chapters, total_c, total_h, is_done):
        if task_id != self.current_task_id: return
        self.chapters = chapters
        
        # 增量刷新目录，避免卡顿
        current_count = len(chapters)
        if current_count > self.last_reported_ch_count:
            for i in range(self.last_reported_ch_count, current_count):
                self.dir_list.insert(tk.END, f" {chapters[i][0]}")
            self.last_reported_ch_count = current_count
        
        if is_done:
            self.stats_var.set(f"全文: {total_c:,}字 | 汉字: {total_h:,}")
            self.status_var.set(os.path.basename(self.current_file))
            self.dir_list.selection_set(self.current_ch_idx)
        else:
            self.stats_var.set(f"解析中: {total_c//10000}万字...")

    def load_chapter_content(self, idx, force_pos=None):
        if not self.file_bytes: return
        start = force_pos if force_pos is not None else self.chapters[idx][1]
        end = self.chapters[idx+1][1] if idx+1 < len(self.chapters) else min(start + 150000, len(self.file_bytes))
            
        try:
            content = self.file_bytes[start:end].decode(self.encoding, errors='ignore').replace('\r\n', '\n')
            self.text.config(state=tk.NORMAL)
            self.text.delete("1.0", tk.END)
            self.text.insert("1.0", content)
            self.update_view_style()
            self.text.config(state=tk.DISABLED)
            
            if force_pos is None: self.current_ch_idx = idx
            self.ch_stats_var.set(f"本章: {len(content.strip())}")
            self.update_progress_label()
        except Exception as e: print(f"Load Error: {e}")

    def locate_current_chapter(self):
        """同步目录并滚动到当前章节"""
        if self.chapters:
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
        self.dir_list.configure(bg=t["l_bg"], fg=t["fg"], selectbackground="#999")
        self.update_view_style()

    def on_chapter_click(self, e):
        sel = self.dir_list.curselection()
        if sel: self.load_chapter_content(sel[0]); self.save_settings()

    def change_chapter(self, delta):
        new_idx = self.current_ch_idx + delta
        if 0 <= new_idx < len(self.chapters): self.load_chapter_content(new_idx); self.save_settings()

    def update_progress_label(self):
        if not self.chapters: return
        p = (self.current_ch_idx + 1) / len(self.chapters) * 100
        self.progress_var.set(f"进度: {p:.1f}%")

    def on_close(self):
        try:
            self.save_settings()
        except Exception as e:
            print(f"Error saving settings: {e}")
        finally:
            self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except: pass
    app = ReaderApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()