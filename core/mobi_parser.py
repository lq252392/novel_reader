import mobi
import os
import threading
import re
import html
from bs4 import BeautifulSoup
from .base_parser import BaseParser

class MobiParser(BaseParser):
    def __init__(self, file_path):
        super().__init__(file_path)
        self.temp_dir = None
        self.html_path = None
        self.chapters = []
        self.chapter_offsets = []

    def scan(self, rule, callback, task_id):
        def _task():
            try:
                # 1. 解压并寻找核心 HTML
                self.temp_dir, self.html_path = mobi.extract(self.file_path)
                
                # 寻找最大的内容文件（通常是正文）
                candidates = []
                for root, dirs, files in os.walk(self.temp_dir):
                    for f in files:
                        if f.endswith(('.xhtml', '.html')):
                            candidates.append(os.path.join(root, f))
                if candidates:
                    self.html_path = max(candidates, key=os.path.getsize)

                # 2. 扫描目录 (为了性能，依然使用正则读取前 5MB)
                with open(self.html_path, 'rb') as f:
                    raw_data = f.read(5000000)
                text_sample = raw_data.decode('utf-8', errors='ignore')
                
                # 剔除干扰
                text_sample = re.sub(r'<(style|script|head)>.*?</\1>', '', text_sample, flags=re.S | re.I)
                
                markers = []
                # 策略 A：锚点法 (大合集常用)
                links = re.findall(r'href=["\']#([^"\']+)["\'][^>]*>(.*?)</a>', text_sample, re.S)
                if len(links) > 5:
                    # 获取全文内容进行定位
                    with open(self.html_path, 'r', encoding='utf-8', errors='ignore') as f:
                        full_txt = f.read()
                        for ref_id, title in links:
                            t = re.sub(r'<[^>]+>', '', title).strip()
                            if 2 < len(t) < 80:
                                pos = full_txt.find(f'id="{ref_id}"')
                                if pos == -1: pos = full_txt.find(f'name="{ref_id}"')
                                if pos != -1: markers.append((pos, t))
                        del full_txt

                # 策略 B：H标签法 (小 MOBI 常用)
                if len(markers) < 5:
                    for m in re.finditer(r'<(h[1-4])[^>]*>(.*?)</\1>', text_sample, re.S | re.I):
                        t = re.sub(r'<[^>]+>', '', m.group(2)).strip()
                        if 1 < len(t) < 60: markers.append((m.start(), t))

                # 排序并去重
                markers = sorted(list(set(markers)), key=lambda x: x[0])

                # 3. 整理结果
                if not markers:
                    size = os.path.getsize(self.html_path)
                    for i in range(0, size, 120000):
                        self.chapters.append((f"第 {i//120000 + 1} 部分", i))
                        self.chapter_offsets.append(i)
                else:
                    last_pos = -1
                    for pos, title in markers:
                        if pos - last_pos > 500:
                            self.chapters.append((html.unescape(title), pos))
                            self.chapter_offsets.append(pos)
                            last_pos = pos

                callback(task_id, self.chapters, os.path.getsize(self.html_path), 0, True)
            except Exception as e:
                print(f"MOBI解析失败: {e}")
        
        threading.Thread(target=_task, daemon=True).start()

    def get_content(self, index):
        if not self.html_path or index >= len(self.chapter_offsets): return []
        
        start = self.chapter_offsets[index]
        end = self.chapter_offsets[index+1] if index+1 < len(self.chapter_offsets) else -1
        
        try:
            with open(self.html_path, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(start)
                # 限制读取量，单章 500KB 足够，且 BeautifulSoup 处理这个量级极快
                chunk = f.read(500000 if end == -1 else min(500000, end - start + 2000))
                
                # 使用 BeautifulSoup 进行精准清洗（仅处理当前片段，不卡顿）
                soup = BeautifulSoup(chunk, 'html.parser')
                
                # 移除样式和脚本
                for s in soup(['style', 'script']): s.decompose()
                
                blocks = []
                # 遍历所有可能的正文和图片标签
                for tag in soup.find_all(['p', 'div', 'img', 'h1', 'h2', 'h3', 'image']):
                    if tag.name in ['img', 'image']:
                        img_data = self._process_img_tag(tag)
                        if img_data: blocks.append(img_data)
                    else:
                        # 仅提取没有子段落标签的文本，防止内容重复提取
                        if not tag.find(['p', 'div']):
                            txt = tag.get_text().strip()
                            if txt and len(txt) > 1:
                                # 彻底过滤残留的 CSS 样式代码
                                if '{' in txt and '}' in txt: continue
                                blocks.append({'type': 'text', 'content': txt})
                
                # 兜底方案：如果 BS4 没解析出东西，说明 HTML 严重损坏
                if not blocks:
                    clean = re.sub(r'<[^>]+>', '\n', chunk)
                    for line in clean.split('\n'):
                        if line.strip(): blocks.append({'type': 'text', 'content': line.strip()})
                
                return blocks
        except Exception as e:
            return [{'type': 'text', 'content': f'读取异常: {e}'}]

    def _process_img_tag(self, tag):
        """精准提取图片二进制数据"""
        # MOBI 常见的图片属性名
        src = tag.get('src') or tag.get('recindex') or tag.get('xlink:href')
        if not src: return None
        
        # 清理路径
        clean_src = str(src).split('/')[-1].replace('../', '').replace('./', '')
        
        # 构建搜索范围 (涵盖 KF8 和旧版 MOBI 提取后的所有可能位置)
        search_dirs = [
            os.path.dirname(self.html_path),
            os.path.join(self.temp_dir, 'mobi8', 'OEBPS', 'Images'),
            os.path.join(self.temp_dir, 'mobi8', 'OEBPS'),
            os.path.join(self.temp_dir, 'mobi7', 'Images'),
            self.temp_dir
        ]
        
        # 尝试匹配文件名
        for d in search_dirs:
            if not os.path.exists(d): continue
            # 1. 直接匹配
            p = os.path.join(d, clean_src)
            if os.path.exists(p) and os.path.isfile(p):
                return self._read_img(p)
            
            # 2. 模糊匹配（忽略大小写和后缀差异，处理 recindex="00001" 这种）
            for f in os.listdir(d):
                if clean_src.lower() in f.lower() or f.lower() in clean_src.lower():
                    return self._read_img(os.path.join(d, f))
        return None

    def _read_img(self, path):
        try:
            with open(path, 'rb') as f:
                data = f.read()
                if len(data) > 100: # 过滤掉损坏的极小图片
                    return {'type': 'img', 'content': data}
        except: pass
        return None
