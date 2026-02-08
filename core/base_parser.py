class BaseParser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.chapters = [] # 格式: [(标题, 字节位置/索引)]
        self.encoding = "utf-8"

    def scan(self, rule, callback, task_id):
        """扫描章节，通过 callback 返回进度"""
        raise NotImplementedError

    def get_content(self, idx):
        """获取指定章节内容"""
        raise NotImplementedError

    def save_content(self, idx, content):
        """保存修改内容（如果支持）"""
        raise NotImplementedError
