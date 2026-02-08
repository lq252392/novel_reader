# ui/app.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import time, os, sys, json, re
from .styles import THEMES, APP_NAME, DEFAULT_REG, REG_TEMPLATES
from core.txt_parser import TxtParser
from utils.config import ConfigManager

class ReaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1300x900")
        
        self.config_repo = ConfigManager()
        self.parser = None
        self.current_file = None
        self.current_ch_idx = 0
        self.is_editing = False
        self.current_task_id = 0
        self.display_chapters = []
        self.is_indexing = False

        self._init_vars()
        self._setup_ui()
        self._bind_events()
        
        # 计时器相关锚点
        self.session_start = time.time()
        self.book_start = time.time()
        self._update_timer()

        # 自动加载
        last = self.config_repo.settings.get("last_file")
        if last and os.path.exists(last):
            self.root.after(300, lambda: self.load_file(last))

    def _init_vars(self):
        s = self.config_repo.settings
        self.font_size = tk.IntVar(value=s.get("font_size", 18))
        self.line_spacing = tk.DoubleVar(value=s.get("line_spacing", 1.6))
        self.theme_name = tk.StringVar(value=s.get("theme", "warm"))
        self.chapter_rule = tk.StringVar(value=s.get("rule", DEFAULT_REG))
        
        self.status_var = tk.StringVar(value="准备就绪")
        self.stats_var = tk.StringVar(value="全书: 0 | 汉字: 0")
        self.progress_var = tk.StringVar()
        self.ch_stats_var = tk.StringVar()
        self.timer_var = tk.StringVar(value="计时初始化...")
        self.ch_inner_progress = tk.StringVar(value="章内: 0%")
        self.search_var = tk.StringVar()
        self.reg_tmpl_var = tk.StringVar(value="标准模式 (推荐)")

    def _setup_ui(self):
        # 1. 底部状态栏
        self.bottom_bar = tk.Frame(self.root, height=30, bg="#222")
        self.bottom_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.bottom_bar.pack_propagate(False)
        
        tk.Label(self.bottom_bar, textvariable=self.status_var, fg="#00ff00", bg="#222", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=10)
        tk.Label(self.bottom_bar, textvariable=self.stats_var, fg="#999", bg="#222", font=("Arial", 9)).pack(side=tk.RIGHT, padx=10)
        tk.Label(self.bottom_bar, textvariable=self.timer_var, fg="#f39c12", bg="#222", font=("Arial", 9, "bold")).pack(side=tk.RIGHT, padx=10)
        tk.Label(self.bottom_bar, textvariable=self.ch_inner_progress, fg="#e74c3c", bg="#222", font=("Arial", 9, "bold")).pack(side=tk.RIGHT, padx=10)
        tk.Label(self.bottom_bar, textvariable=self.ch_stats_var, fg="#3498db", bg="#222", font=("Arial", 9, "bold")).pack(side=tk.RIGHT, padx=10)
        tk.Label(self.bottom_bar, textvariable=self.progress_var, fg="#999", bg="#222", font=("Arial", 9)).pack(side=tk.RIGHT, padx=10)

        # 2. 顶部工具栏
        self.toolbar = ttk.Frame(self.root, padding=5)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(self.toolbar, text="📂 打开", width=7, command=self.open_file_dialog).pack(side=tk.LEFT, padx=2)
        self.edit_btn = ttk.Button(self.toolbar, text="📝 编辑 (E)", width=10, command=self.toggle_edit)
        self.edit_btn.pack(side=tk.LEFT, padx=2)
        self.save_btn = ttk.Button(self.toolbar, text="💾 保存", width=7, state=tk.DISABLED, command=self.save_edit)
        self.save_btn.pack(side=tk.LEFT, padx=2)
        
        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # 主题与字号
        ttk.Label(self.toolbar, text="字号:").pack(side=tk.LEFT)
        ttk.Spinbox(self.toolbar, from_=10, to=60, width=3, textvariable=self.font_size, command=self.apply_style).pack(side=tk.LEFT, padx=2)
        
        theme_cb = ttk.Combobox(self.toolbar, textvariable=self.theme_name, values=list(THEMES.keys()), width=7, state="readonly")
        theme_cb.pack(side=tk.LEFT, padx=5)
        theme_cb.bind("<<ComboboxSelected>>", lambda e: self.apply_style())

        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        # 正则模板
        reg_combo = ttk.Combobox(self.toolbar, textvariable=self.reg_tmpl_var, values=list(REG_TEMPLATES.keys()), width=15, state="readonly")
        reg_combo.pack(side=tk.LEFT, padx=2)
        reg_combo.bind("<<ComboboxSelected>>", self._on_template_change)
        
        ttk.Entry(self.toolbar, textvariable=self.chapter_rule).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
        ttk.Button(self.toolbar, text="↺", width=3, command=self._reset_reg).pack(side=tk.LEFT, padx=2)
        ttk.Button(self.toolbar, text="解析", width=5, command=self.re_index).pack(side=tk.LEFT, padx=2)

        # 3. 中间主体
        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)
        
        # 左侧目录
        self.left_frame = tk.Frame(self.paned)
        tk.Entry(self.left_frame, textvariable=self.search_var).pack(fill=tk.X, padx=5, pady=5)
        self.search_var.trace_add("write", lambda *a: self.refresh_dir())
        self.dir_list = tk.Listbox(self.left_frame, width=30, borderwidth=0, font=("Microsoft YaHei", 10))
        self.dir_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        dir_scroll = ttk.Scrollbar(self.left_frame, command=self.dir_list.yview)
        dir_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.dir_list.config(yscrollcommand=dir_scroll.set)
        self.dir_list.bind("<<ListboxSelect>>", self.on_dir_click)
        self.paned.add(self.left_frame, weight=1)

        # 右侧正文
        self.right_frame = tk.Frame(self.paned)
        self.text_scroll = ttk.Scrollbar(self.right_frame)
        self.text_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.text = tk.Text(self.right_frame, wrap=tk.WORD, undo=True, borderwidth=0, 
                            padx=50, pady=30, yscrollcommand=self._on_scroll_sync)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.text_scroll.config(command=self.text.yview)
        self.paned.add(self.right_frame, weight=4)
        
        self.apply_style() # 初始化应用主题

    def _on_scroll_sync(self, *args):
        self.text_scroll.set(*args)
        try:
            top, bottom = float(args[0]), float(args[1])
            percent = 100 if bottom >= 0.99 else int(bottom * 100)
            self.ch_inner_progress.set(f"章内: {percent}%")
        except: pass

        # --- 渲染优化逻辑 ---
    def _format_content_for_read(self, raw_text):
        """清洗正文：仅删除空行和首尾杂质，不再手动加空格"""
        if not raw_text: return ""
        lines = raw_text.splitlines()
        clean_lines = []
        for line in lines:
            s = line.strip()
            if not s: continue 
            clean_lines.append(s) # 这里不加空格，由 Text 控件的缩进控制
        return "\n".join(clean_lines)

    def _apply_visual_kerning(self):
        """标点外挂：让引号行向左偏移 0.5 个字符，对标业内顶尖阅读 App"""
        sz = self.font_size.get()
        
        # 1. 设置基础正文标签：首行缩进 2 个字符
        self.text.tag_configure("para_normal", lmargin1=sz * 2, lmargin2=0)
        
        # 2. 设置引号外挂标签：首行缩进 1.5 个字符 (外挂 0.5 个字符)
        # 这样文本内容其实还是在 2.0 的位置对齐，只是引号突出去一点
        self.text.tag_configure("para_quote", lmargin1=sz * 1.5, lmargin2=0) 

        # 清除之前的旧标签（防止切换章节后重叠）
        for tag in ["para_normal", "para_quote"]:
            self.text.tag_remove(tag, "1.0", tk.END)

        idx = "1.0"
        while True:
            # 搜索每一行的开头
            line_start = self.text.search(r"^.", idx, stopindex=tk.END, regexp=True)
            if not line_start: break
            
            line_num = line_start.split('.')[0]
            # 获取该行第一个字符
            first_char = self.text.get(line_start)
            
            # 判断是否为引号/特殊标点
            if first_char in '“「『"‘':
                self.text.tag_add("para_quote", f"{line_num}.0", f"{line_num}.end")
            else:
                self.text.tag_add("para_normal", f"{line_num}.0", f"{line_num}.end")
                
            idx = f"{line_num}.end+1c" # 移动到下一行开头

    def show_chapter(self, idx):
        if not self.parser: return
        if not self.parser.chapters: idx = 0
        else:
            idx = max(0, min(idx, len(self.parser.chapters) - 1))
            
        self.current_ch_idx = idx
        raw_content = self.parser.get_content(idx)
        
        # 渲染逻辑
        display_content = raw_content
        if not self.is_editing:
            display_content = self._format_content_for_read(raw_content)

        self.text.config(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", display_content)
        
        if not self.is_editing:
            self.text.config(state=tk.DISABLED)
            # 必须先 apply_style 再 apply_visual_kerning，因为后者依赖当前的字号
            self.apply_style()
            self._apply_visual_kerning()
        else:
            self.apply_style()
            
        self.ch_stats_var.set(f"本章: {len(raw_content):,}字")
        self.progress_var.set(f"进度: {idx+1}/{len(self.parser.chapters) if self.parser.chapters else 1}章")
        self.refresh_dir()


    # --- 定位与解析 ---
    def load_file(self, path):
        if self.current_file: self.save_session_settings()
        self.current_file = path
        self.parser = TxtParser(path)
        self.book_start = time.time()
        
        f_cfg = self.config_repo.settings.get("files", {}).get(path, {})
        self.temp_saved_idx = f_cfg.get("ch_idx", 0)
        self.temp_saved_offset = f_cfg.get("offset", 0.0)
        self.temp_saved_byte = f_cfg.get("byte_pos", 0)
        
        self.current_ch_idx = self.temp_saved_idx
        self.re_index()
        self.show_chapter(self.current_ch_idx)

    def re_index(self):
        if not self.parser: return
        self.is_indexing = True
        self.current_task_id += 1
        self.status_var.set("正在解析目录...")
        self.parser.scan(self.chapter_rule.get(), self._index_callback, self.current_task_id)

    def _index_callback(self, tid, chapters, tc, th, done):
        if tid != self.current_task_id: return
        self.root.after(0, lambda: self._sync_ui(tc, th, done))

    def _sync_ui(self, tc, th, done):
        if done:
            self.is_indexing = False
            self.status_var.set(os.path.basename(self.current_file))
            # 修复：显示全书字数和汉字数
            self.stats_var.set(f"全书: {tc:,} | 汉字: {th:,}")
            
            if hasattr(self, 'temp_saved_byte'):
                best_idx = 0
                for i, (title, pos) in enumerate(self.parser.chapters):
                    if pos <= self.temp_saved_byte: best_idx = i
                    else: break
                self.current_ch_idx = best_idx
                self.show_chapter(self.current_ch_idx)
                self.root.after(150, lambda: self.text.yview_moveto(self.temp_saved_offset))
                delattr(self, 'temp_saved_byte')
            self.refresh_dir()
        else:
            self.stats_var.set(f"索引中: {tc//10000}万字...")

    # --- 样式与计时 ---
    def apply_style(self, _=None):
        t = THEMES.get(self.theme_name.get(), THEMES["warm"])
        sz = self.font_size.get()
        line_sp = int(sz * (self.line_spacing.get() - 1))
        
        # 更新正文
        self.text.config(bg=t["bg"], fg=t["fg"], font=("Microsoft YaHei", sz), 
                         spacing1=sz, spacing2=line_sp, spacing3=0, insertbackground=t["fg"])
        # 更新背景容器，实现主题全覆盖
        self.left_frame.config(bg=t["l_bg"])
        self.right_frame.config(bg=t["bg"])
        self.dir_list.config(bg=t["l_bg"], fg=t["fg"], selectbackground=t["select"])
        
        # 默认缩进
        self.text.tag_configure("in", lmargin1=sz*2, lmargin2=0)

    def _update_timer(self):
        if self.current_file:
            now = time.time()
            # 本场时间
            s_min = int((now - self.session_start) / 60)
            # 本书总时间
            f_cfg = self.config_repo.settings.get("files", {}).get(self.current_file, {})
            history_time = f_cfg.get("total_time", 0)
            b_min = int((history_time + (now - self.book_start)) / 60)
            self.timer_var.set(f"本场: {s_min}分 | 本书: {b_min}分")
        else:
            self.timer_var.set("等待阅读...")
        self.root.after(10000, self._update_timer)

    # --- 其他逻辑 ---
    def _on_template_change(self, e=None):
        new_reg = REG_TEMPLATES.get(self.reg_tmpl_var.get(), DEFAULT_REG)
        self.chapter_rule.set(new_reg)
        self.re_index()

    def _reset_reg(self):
        self.chapter_rule.set(DEFAULT_REG)
        self.reg_tmpl_var.set("标准模式 (推荐)")
        self.re_index()

    def refresh_dir(self):
        if not self.parser: return
        search = self.search_var.get().lower()
        self.dir_list.delete(0, tk.END)
        self.display_chapters = []
        for i, (title, pos) in enumerate(self.parser.chapters):
            if not search or search in title.lower():
                self.display_chapters.append(i)
                self.dir_list.insert(tk.END, f" {title}")
        for i, orig_idx in enumerate(self.display_chapters):
            if orig_idx == self.current_ch_idx:
                self.dir_list.selection_set(i); self.dir_list.see(i); break

    def save_session_settings(self):
        if not self.parser or not self.current_file: return
        f_map = self.config_repo.settings.get("files", {})
        try:
            scroll_pos = self.text.yview()[0]
            byte_pos = self.parser.chapters[self.current_ch_idx][1] if self.current_ch_idx < len(self.parser.chapters) else 0
        except: scroll_pos = 0.0; byte_pos = 0
        
        old_time = f_map.get(self.current_file, {}).get("total_time", 0)
        f_map[self.current_file] = {
            "ch_idx": self.current_ch_idx, 
            "byte_pos": byte_pos, 
            "offset": scroll_pos,
            "total_time": old_time + int(time.time() - self.book_start)
        }
        self.config_repo.save({
            "font_size": self.font_size.get(), 
            "theme": self.theme_name.get(), 
            "rule": self.chapter_rule.get(), 
            "last_file": self.current_file, 
            "files": f_map
        })
        self.book_start = time.time()

    def open_file_dialog(self):
        p = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if p: self.load_file(p)

    def toggle_edit(self):
        if not self.parser: return
        self.is_editing = not self.is_editing
        self.edit_btn.config(text="📖 退出编辑" if self.is_editing else "📝 编辑 (E)")
        self.save_btn.config(state=tk.NORMAL if self.is_editing else tk.DISABLED)
        self.show_chapter(self.current_ch_idx)

    def save_edit(self):
        if self.parser and self.is_editing:
            if self.parser.save_content(self.current_ch_idx, self.text.get("1.0", tk.END)):
                messagebox.showinfo("成功", "内容已保存"); self.re_index()

    def change_chapter(self, delta):
        if not self.is_editing: self.show_chapter(self.current_ch_idx + delta)

    def on_dir_click(self, e):
        sel = self.dir_list.curselection()
        if sel: self.show_chapter(self.display_chapters[sel[0]])

    def _bind_events(self):
        self.root.bind("<KeyPress-Left>", lambda e: self.change_chapter(-1))
        self.root.bind("<KeyPress-Right>", lambda e: self.change_chapter(1))
        self.root.bind("e", lambda e: self.toggle_edit())
        self.root.bind("<Control-s>", lambda e: self.save_edit())
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        self.save_session_settings()
        self.root.destroy()
