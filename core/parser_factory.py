import os
from core.txt_parser import TxtParser
from core.epub_parser import EpubParser
from core.mobi_parser import MobiParser

class ParserFactory:
    @staticmethod
    def get_parser(file_path):
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.txt':
            return TxtParser(file_path)
        elif ext == '.epub':
            return EpubParser(file_path)
        elif ext in ['.mobi', '.azw', '.azw3']:
            # 目前暂时用 Epub 逻辑尝试解析，或提示不支持
            return MobiParser(file_path) 
        else:
            raise ValueError(f"不支持的格式: {ext}")
