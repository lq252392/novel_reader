import os
import re
import json
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import chardet
except ImportError:
    chardet = None

APP_NAME = "极速阅读器 Pro"
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "reader_settings.json")

class FastTextIndexer:
    """增强型索引器：支持进度反馈和中断"""
    def __init__(self, file_path, encoding, rule):
        self.file_path = file_path
        self.encoding = encoding
        self.rule = re.compile(rule.encode(encoding, errors='ignore'))
        self.chapters = []
        self.total_chars = 0
        self.total_han = 0
        self.is_running = True

    def scan(self, callback):
        try:
            with open(self.file_path, 'rb') as f:
                self.chapters.append(("正文开始", 0))
                line_count = 0
                while self.is_running:
                    pos = f.tell()
                    line = f.readline()
                    if not line: break
                    
                    try:
                        # 仅在必要时解码，提升扫描性能
                        if self.rule.match(line):
                            title = line.decode(self.encoding, errors='ignore').strip()
                            self.chapters.append((title, pos))
                        
                        # 粗略统计字数（按字节估算或抽样解码）
                        if line_count % 10 == 0:
                            decoded = line.decode(self.encoding, errors='ignore')
                            self.total_chars += len(decoded)
                            self.total_han += len(re.findall(r'[\u4e00-\u9fff]', decoded))
                    except:
                        pass
                    
                    line_count += 1
                    if line_count % 3000 == 0:
                        callback(self.chapters, self.total_chars, self.total_han, False)
                
                callback(self.chapters, self.total_chars, self.total_han, True)
        except Exception as e:
            print(f"Indexer Error: {e}")

class ReaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1200x850")
        
        # --- 核心数据 ---
        self.current_file = None
        self.file_bytes = b""
        self.encoding = "utf-8"
        self.chapters = []
        self.current_ch_idx = 0
        self.indexer = None
        
        self.settings = self.load_settings()
        
        # --- UI 响应式变量 ---
        self.font_size = tk.IntVar(value=self.settings.get("font_size", 18))
        self.line_spacing = tk.DoubleVar(value=self.settings.get("line_spacing", 1.6))
        self.theme = tk.StringVar(value=self.settings.get("theme", "warm"))
        self.chapter_rule = tk.StringVar(value=self.settings.get("rule", r"^(第[〇零一二三四五六七八九十百千万0-9]+[章节回卷篇].*)"))
        
        self.status_var = tk.StringVar(value="就绪")
        self.stats_var = tk.StringVar(value="等待统计...")
        self.ch_stats_var = tk.StringVar(value="本章: 0")
        self.progress_var = tk.StringVar(value="进度: 0.0%")

        self._setup_styles()
        self._setup_ui()
        self.apply_theme()
        
        # 延迟加载上次文件
        last_file = self.settings.get("last_file")
        if last_file and os.path.exists(last_file):
            self.root.after(200, lambda: self.open_file(last_file))

    def _setup_styles(self):
        """全局UI字号调节"""
        style = ttk.Style()
        ui_font_size = 12
        style.configure("TButton", font=("Microsoft YaHei", ui_font_size))
        style.configure("TLabel", font=("Microsoft YaHei", ui_font_size))
        style.configure("TSpinbox", font=("Microsoft YaHei", ui_font_size))
        style.configure("TCombobox", font=("Microsoft YaHei", ui_font_size))

    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        return {}

    def save_settings(self):
        if not self.current_file: return
        self.settings["font_size"] = self.font_size.get()
        self.settings["line_spacing"] = self.line_spacing.get()
        self.settings["theme"] = self.theme.get()
        self.settings["rule"] = self.chapter_rule.get()
        self.settings["last_file"] = self.current_file
        
        if "files" not in self.settings: self.settings["files"] = {}
        # 关键优化：保存当前章节的绝对字节位置
        byte_pos = self.chapters[self.current_ch_idx][1] if self.current_ch_idx < len(self.chapters) else 0
        self.settings["files"][self.current_file] = {
            "ch_idx": self.current_ch_idx,
            "byte_pos": byte_pos,
            "offset": self.text.yview()[0]
        }
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except: pass

    def _setup_ui(self):
        # 1. 底部栏 (最先布局，固定高度)
        bottom_bar = tk.Frame(self.root, height=40, bg="#222")
        bottom_bar.pack(side=tk.BOTTOM, fill=tk.X)
        bottom_bar.pack_propagate(False)

        tk.Label(bottom_bar, textvariable=self.status_var, fg="#00ff00", bg="#222", font=("Microsoft YaHei", 10, "bold")).pack(side=tk.LEFT, padx=15)
        tk.Label(bottom_bar, textvariable=self.stats_var, fg="#ccc", bg="#222", font=("Microsoft YaHei", 10)).pack(side=tk.RIGHT, padx=15)
        tk.Label(bottom_bar, textvariable=self.ch_stats_var, fg="#ccc", bg="#222", font=("Microsoft YaHei", 10)).pack(side=tk.RIGHT, padx=15)
        tk.Label(bottom_bar, textvariable=self.progress_var, fg="#ccc", bg="#222", font=("Microsoft YaHei", 10)).pack(side=tk.RIGHT, padx=15)

        # 2. 顶部工具栏
        toolbar = ttk.Frame(self.root, padding=5)
        toolbar.pack(side=tk.TOP, fill=tk.X)
        
        ttk.Button(toolbar, text="📂 打开", command=self.open_file_dialog, width=8).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        ttk.Label(toolbar, text="字号:").pack(side=tk.LEFT)
        ttk.Spinbox(toolbar, from_=10, to=60, width=4, textvariable=self.font_size, command=self.update_view_style).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(toolbar, text="行距:").pack(side=tk.LEFT, padx=(10,0))
        ttk.Spinbox(toolbar, from_=1.0, to=3.5, increment=0.1, width=4, textvariable=self.line_spacing, command=self.update_view_style).pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        theme_sel = ttk.Combobox(toolbar, textvariable=self.theme, values=["warm", "green", "dark", "paper"], width=8, state="readonly")
        theme_sel.pack(side=tk.LEFT, padx=2)
        theme_sel.bind("<<ComboboxSelected>>", lambda e: self.apply_theme())

        ttk.Entry(toolbar, textvariable=self.chapter_rule, width=15).pack(side=tk.LEFT, padx=10)
        ttk.Button(toolbar, text="重新解析", command=self.re_index).pack(side=tk.LEFT)
        
        # 3. 中间主体
        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)

        # 左侧目录区 (增加滚动条和定位按钮)
        left_frame = tk.Frame(self.paned)
        self.dir_list = tk.Listbox(left_frame, width=30, font=("Microsoft YaHei", 10), 
                                  borderwidth=0, bg="#eee", selectbackground="#666", activestyle='none')
        self.dir_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.dir_list.bind("<<ListboxSelect>>", self.on_chapter_click)
        
        dir_scroll = ttk.Scrollbar(left_frame, command=self.dir_list.yview)
        dir_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.dir_list.config(yscrollcommand=dir_scroll.set)
        
        # 定位按钮悬浮在目录上方
        btn_locate = tk.Button(left_frame, text="🎯 定位当前", font=("Microsoft YaHei", 9),
                              command=self.locate_current_chapter, bg="#ddd", relief=tk.GROOVE)
        btn_locate.place(relx=0.5, rely=0.02, anchor=tk.N)

        self.paned.add(left_frame, weight=1)

        # 右侧文本区
        text_frame = tk.Frame(self.paned)
        self.text = tk.Text(text_frame, wrap=tk.WORD, borderwidth=0, highlightthickness=0,
                           padx=35, pady=25, undo=True, font=("Microsoft YaHei", self.font_size.get()))
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        main_scroll = ttk.Scrollbar(text_frame, command=self.text.yview)
        main_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.config(yscrollcommand=main_scroll.set)
        self.paned.add(text_frame, weight=4)

        # 快捷键绑定
        self.root.bind("<KeyPress-Left>", lambda e: self.change_chapter(-1))
        self.root.bind("<KeyPress-Right>", lambda e: self.change_chapter(1))
        self.text.bind("<MouseWheel>", lambda e: self.root.after(100, self.update_progress_label))

    def open_file(self, path):
        if self.indexer: self.indexer.is_running = False
        self.current_file = path
        self.status_var.set("正在读取...")
        
        with open(path, 'rb') as f:
            self.file_bytes = f.read()
        
        self.encoding = self.detect_encoding(self.file_bytes[:30000])
        
        # 恢复逻辑优化：优先寻找绝对字节位置
        file_info = self.settings.get("files", {}).get(path, {})
        saved_byte_pos = file_info.get("byte_pos", 0)
        self.current_ch_idx = file_info.get("ch_idx", 0)
        
        # 如果有保存的字节位置，立即加载该位置的内容，不等待索引
        if saved_byte_pos > 0:
            self.chapters = [("正在找回进度...", saved_byte_pos)]
            self.load_chapter_content(0, force_pos=saved_byte_pos)
        else:
            self.chapters = [("正文开始", 0)]
            self.load_chapter_content(0)

        self.re_index()
        
        offset = file_info.get("offset", 0.0)
        self.root.after(300, lambda: self.text.yview_moveto(offset))

    def detect_encoding(self, chunk):
        if chardet:
            res = chardet.detect(chunk)
            if res['confidence'] > 0.6: return res['encoding']
        for enc in ['utf-8', 'gbk', 'gb18030', 'utf-16']:
            try: chunk.decode(enc); return enc
            except: pass
        return 'utf-8'

    def re_index(self):
        if not self.current_file: return
        self.indexer = FastTextIndexer(self.current_file, self.encoding, self.chapter_rule.get())
        t = threading.Thread(target=self.indexer.scan, args=(self.update_ui_callback,), daemon=True)
        t.start()

    def update_ui_callback(self, chapters, total_c, total_h, is_done):
        self.chapters = chapters
        if is_done or len(chapters) % 15 == 0:
            self.dir_list.delete(0, tk.END)
            for title, pos in chapters:
                self.dir_list.insert(tk.END, f" {title}")
            # 尝试同步选择项
            if self.current_ch_idx < len(self.chapters):
                self.dir_list.selection_set(self.current_ch_idx)
            
        if is_done:
            self.stats_var.set(f"全文: {total_c}字 | 汉字: {total_h}")
            self.status_var.set(os.path.basename(self.current_file))

    def load_chapter_content(self, idx, force_pos=None):
        if not self.file_bytes: return
        
        # 确定起始位
        start = force_pos if force_pos is not None else self.chapters[idx][1]
        
        # 确定结束位：如果下一章还没扫出来，默认读 100KB 防止“章节不完整”
        if idx + 1 < len(self.chapters):
            end = self.chapters[idx+1][1]
        else:
            end = min(start + 100000, len(self.file_bytes)) 
            
        try:
            raw_chunk = self.file_bytes[start:end]
            # 解决乱码：如果在多字节字符中间切断，decode会报错，errors='ignore'可跳过损坏部分
            content = raw_chunk.decode(self.encoding, errors='ignore').replace('\r\n', '\n')
            
            self.text.config(state=tk.NORMAL)
            self.text.delete("1.0", tk.END)
            self.text.insert("1.0", content)
            self.update_view_style()
            self.text.config(state=tk.DISABLED)
            
            if force_pos is None: self.current_ch_idx = idx
            self.ch_stats_var.set(f"本章: {len(content.strip())}")
            self.update_progress_label()
        except Exception as e:
            print(f"Load Error: {e}")

    def locate_current_chapter(self):
        """同步目录列表到当前阅读章节"""
        if self.chapters:
            self.dir_list.selection_clear(0, tk.END)
            self.dir_list.selection_set(self.current_ch_idx)
            self.dir_list.see(self.current_ch_idx)

    def update_view_style(self, _=None):
        f_size = self.font_size.get()
        s_val = int(f_size * (self.line_spacing.get() - 1))
        self.text.configure(font=("Microsoft YaHei", f_size), spacing2=s_val, spacing1=5, spacing3=5)
        self.save_settings()

    def apply_theme(self):
        themes = {
            "warm": {"bg": "#f4f0e6", "fg": "#332c22", "l_bg": "#ede7da"},
            "green": {"bg": "#e8f5e9", "fg": "#1b5e20", "l_bg": "#dcedc8"},
            "dark": {"bg": "#1a1a1a", "fg": "#bbb", "l_bg": "#252525"},
            "paper": {"bg": "#fafafa", "fg": "#111", "l_bg": "#eee"}
        }
        t = themes.get(self.theme.get(), themes["warm"])
        self.text.configure(bg=t["bg"], fg=t["fg"], insertbackground=t["fg"])
        self.dir_list.configure(bg=t["l_bg"], fg=t["fg"])
        self.update_view_style()

    def on_chapter_click(self, e):
        sel = self.dir_list.curselection()
        if sel: 
            self.load_chapter_content(sel[0])
            self.save_settings()

    def change_chapter(self, delta):
        new_idx = self.current_ch_idx + delta
        if 0 <= new_idx < len(self.chapters):
            self.load_chapter_content(new_idx)
            self.save_settings()

    def open_file_dialog(self):
        p = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if p: self.open_file(p)

    def update_progress_label(self):
        if not self.chapters: return
        p = (self.current_ch_idx + 1) / len(self.chapters) * 100
        self.progress_var.set(f"进度: {p:.1f}%")

    def on_close(self):
        self.save_settings()
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
