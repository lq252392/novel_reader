# ui/styles.py

DEFAULT_REG = r'(?:第?\s*[0-9一二三四五六七八九十百千零]+\s*[章节回卷集部篇幕])|(?:\bChapter\s*[0-9]+)'

# 预设正则模板
REG_TEMPLATES = {
    "标准模式 (推荐)": r'(?:第?\s*[0-9一二三四五六七八九十百千零]+\s*[章节回卷集部篇幕])|(?:\bChapter\s*[0-9]+)',
    "严谨模式 (必须行首)": r'^第[0-9一二三四五六七八九十百千零]+[章节回卷集部篇幕].*',
    "简洁模式 (仅数字)": r'^\s*[0-9]+\s*$',
    "英文模式 (Chapter)": r'^\s*Chapter\s*[0-9]+.*'
}

THEMES = {
    "warm": {"bg": "#f4ecd8", "fg": "#3e2e1c", "l_bg": "#e9dfc7", "select": "#d5c5a0"},
    "green": {"bg": "#c7edcc", "fg": "#1a2e1a", "l_bg": "#b8e2bd", "select": "#a5d5ac"},
    "dark": {"bg": "#1a1a1a", "fg": "#999999", "l_bg": "#252525", "select": "#333333"},
    "white": {"bg": "#ffffff", "fg": "#333333", "l_bg": "#f0f0f0", "select": "#e0e0e0"}
}

APP_NAME = "极简阅读器 v5.2"
