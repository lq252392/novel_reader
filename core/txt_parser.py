import re, threading
from .base_parser import BaseParser
from utils.detector import detect_encoding

class TxtParser(BaseParser):
    def __init__(self, file_path):
        super().__init__(file_path)
        with open(file_path, 'rb') as f:
            self.file_bytes = f.read()
        self.encoding = detect_encoding(self.file_bytes[:30000])
        self.is_running = False # 任务运行标志


    def scan(self, rule, callback, task_id):
        self.is_running = True 
        
        def _work():
            chapters = [("正文开始", 0)]
            total_chars, total_han = 0, 0
            
            try:
                import re
                reg = re.compile(rule)
            except:
                # 线程内最后的防线：如果编译失败，告知UI索引已完成（空结果）
                self.chapters = chapters
                callback(task_id, chapters, 0, 0, True)
                return


            lines = self.file_bytes.splitlines(keepends=True)
            curr_pos = 0
            
            for i, line_byte in enumerate(lines):
                if not self.is_running: return # 收到停止信号，退出线程
                
                try:
                    line_str = line_byte.decode(self.encoding, errors='ignore')
                    if reg.match(line_str):
                        if curr_pos != 0: chapters.append((line_str.strip(), curr_pos))
                    
                    total_chars += len(line_str)
                    if i % 10 == 0:
                        total_han += len(re.findall(r'[\u4e00-\u9fff]', line_str))
                except: pass
                
                curr_pos += len(line_byte)
                if i % 8000 == 0:
                    callback(task_id, list(chapters), total_chars, total_han, False)
            
            self.chapters = chapters
            callback(task_id, chapters, total_chars, total_han, True)

        threading.Thread(target=_work, daemon=True).start()

    def stop_scan(self):
        self.is_running = False


    def get_content(self, idx):
        if not self.chapters: return ""
        start = self.chapters[idx][1]
        end = self.chapters[idx+1][1] if idx+1 < len(self.chapters) else len(self.file_bytes)
        raw = self.file_bytes[start:end].decode(self.encoding, errors='ignore').replace('\r\n', '\n')
        return "\n".join([l.strip() for l in raw.split('\n')])

    def save_content(self, idx, content):
        new_bytes = (content.strip() + "\n\n").encode(self.encoding, errors='ignore')
        start = self.chapters[idx][1]
        end = self.chapters[idx+1][1] if idx+1 < len(self.chapters) else len(self.file_bytes)
        self.file_bytes = self.file_bytes[:start] + new_bytes + self.file_bytes[end:]
        with open(self.file_path, 'wb') as f:
            f.write(self.file_bytes)
        return True
