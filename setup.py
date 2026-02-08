import sys
import os
from cx_Freeze import setup, Executable

# 明确指定需要包含的额外文件
include_files = []


build_exe_options = {
    "packages": ["tkinter", "os", "sys", "json", "re", "threading", "time", "ebooklib", "bs4", "mobi"],
    "excludes": ["tkinter.test", "tkinter.tests", "test", "unittest", "email", "xml", "distutils"],
    "include_files": include_files,
    "optimize": 2,
    "build_exe": "build/NovelReader",  # 使用英文目录名避免路径问题
    "silent": True,  # 减少输出信息
}

setup(
    name="NovelReader",
    version="4.2",
    description="Novel Reader - Support TXT/EPUB/MOBI formats",
    options={"build_exe": build_exe_options},
    executables=[Executable("main.py", base="Win32GUI", target_name="NovelReader.exe")],
    # 明确指定只打包必要的文件
    include_package_data=False,
)