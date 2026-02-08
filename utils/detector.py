import re

try:
    import chardet
except ImportError:
    chardet = None

def detect_encoding(chunk):
    if chardet:
        res = chardet.detect(chunk)
        if res['confidence'] > 0.6:
            return res['encoding']
    for enc in ['utf-8', 'gbk', 'gb18030']:
        try:
            chunk.decode(enc)
            return enc
        except:
            pass
    return 'utf-8'

def count_chinese_chars(text):
    return len(re.findall(r'[\u4e00-\u9fff]', text))
