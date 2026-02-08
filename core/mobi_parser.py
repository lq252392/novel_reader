# core/mobi_parser.py
import mobi
from bs4 import BeautifulSoup
from .base_parser import BaseParser
import threading, os

class MobiParser(BaseParser):
    def __init__(self, file_path):
        super().__init__(file_path)
        self.html_content = ""

    def scan(self, rule, callback, task_id):
        def _task():
            try:
                # mobi 库会将文件解压到临时路径
                tempdir, filepath = mobi.extract(self.file_path)
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    self.html_content = f.read()
                
                soup = BeautifulSoup(self.html_content, 'html.parser')
                # MOBI 结构通常较杂，简单按 <h1> 分割或视为单章
                # 这里为了简化，暂时将其内容作为单章处理，或按 <mbp:pagebreak> 逻辑分割
                self.chapters = [("正文内容", 0)]
                text = soup.get_text()
                callback(task_id, self.chapters, len(text), len(text), True)
            except: pass
        threading.Thread(target=_task, daemon=True).start()

    def get_content(self, index):
        soup = BeautifulSoup(self.html_content, 'html.parser')
        return soup.get_text(separator='\n').strip()