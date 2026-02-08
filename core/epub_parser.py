import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from .base_parser import BaseParser
import threading

class EpubParser(BaseParser):
    def __init__(self, file_path):
        super().__init__(file_path)
        self.items = []

    def scan(self, rule, callback, task_id):
        def _task():
            try:
                book = epub.read_epub(self.file_path)
                # 过滤出正文文档
                self.items = [item for item in book.get_items() if item.get_type() == ebooklib.ITEM_DOCUMENT]
                
                self.chapters = []
                total_chars = 0
                for i, item in enumerate(self.items):
                    soup = BeautifulSoup(item.get_content(), 'html.parser')
                    # 尝试寻找标题
                    h = soup.find(['h1', 'h2', 'h3', 'title'])
                    title = h.get_text().strip() if h else f"第 {i+1} 章节"
                    if len(title) > 50: title = title[:50] + "..."
                    
                    self.chapters.append((title, i)) # EPUB 的 pos 就是索引
                    total_chars += len(soup.get_text())
                
                callback(task_id, self.chapters, total_chars, total_chars, True)
            except Exception as e:
                print(f"EPUB解析出错: {e}")
        
        threading.Thread(target=_task, daemon=True).start()

    def get_content(self, index):
        if 0 <= index < len(self.items):
            soup = BeautifulSoup(self.items[index].get_content(), 'html.parser')
            # 这里的 get_text(separator='\n') 保证了 HTML 的段落能换行
            return soup.get_text(separator='\n').strip()
        return ""
