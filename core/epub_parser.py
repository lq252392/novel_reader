import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from .base_parser import BaseParser
import threading

class EpubParser(BaseParser):
    def __init__(self, file_path):
        super().__init__(file_path)
        self.book = None
        self.items = []

    def scan(self, rule, callback, task_id):
        def _task():
            try:
                self.book = epub.read_epub(self.file_path)
                # 只获取文档类型的项目
                self.items = [item for item in self.book.get_items() if item.get_type() == ebooklib.ITEM_DOCUMENT]
                
                self.chapters = []
                # 【优化】不再解析 HTML 找标题，直接使用 EPUB 的文件名或索引
                # 这样加载目录是瞬间完成的
                for i, item in enumerate(self.items):
                    # 如果想获取真实标题，只读取前 2048 字节进行简单正则匹配，而不是 BeautifulSoup
                    title = f"第 {i+1} 章节"
                    self.chapters.append((title, i))
                
                callback(task_id, self.chapters, 0, 0, True)
            except Exception as e:
                print(f"EPUB解析出错: {e}")
        
        threading.Thread(target=_task, daemon=True).start()

    def get_content(self, index):
        """只有在看这一章时，才解析这一章的 HTML"""
        if 0 <= index < len(self.items):
            soup = BeautifulSoup(self.items[index].get_content(), 'html.parser')
            blocks = []
            for tag in soup.find_all(['p', 'img', 'h1', 'h2', 'h3']):
                if tag.name == 'img':
                    src = tag.get('src', '').split('/')[-1]
                    for img_item in self.book.get_items_of_type(ebooklib.ITEM_IMAGE):
                        if src in img_item.file_name:
                            blocks.append({'type': 'img', 'content': img_item.get_content()})
                            break
                else:
                    txt = tag.get_text().strip()
                    if txt: blocks.append({'type': 'text', 'content': txt})
            return blocks
        return []
