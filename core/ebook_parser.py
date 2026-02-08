from .base_parser import BaseParser

class EbookParser(BaseParser):
    def scan(self, rule, callback, task_id):
        # 未来集成 ebooklib 逻辑
        pass

    def get_content(self, idx):
        return "EPUB/MOBI 格式支持正在开发中..."
