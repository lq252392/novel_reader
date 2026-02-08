from abc import ABC, abstractmethod

class BaseParser(ABC):
    def __init__(self, file_path):
        self.file_path = file_path
        self.chapters = [] # 存储结构: [(标题, 索引/偏移), ...]

    @abstractmethod
    def scan(self, rule, callback, task_id):
        """异步解析目录结构"""
        pass

    @abstractmethod
    def get_content(self, index):
        """获取指定章节的纯文本内容"""
        pass

    def save_content(self, index, text):
        """默认不支持保存，仅 TXT 子类重写此方法"""
        return False
