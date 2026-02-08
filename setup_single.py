import sys
import os
from cx_Freeze import setup, Executable

# 明确指定需要包含的额外文件
include_files = []


build_exe_options = {
    "packages": ["tkinter", "os", "sys", "json", "re", "threading", "time"],
    "excludes": ["tkinter.test", "tkinter.tests", "test", "unittest", "email", "xml", "distutils"],
    "include_files": include_files,
    "optimize": 2,
    "build_exe": "build/极速小说阅读器-单文件版",  # 构建文件放在build目录下
    "silent": True,  # 减少输出信息
}

setup(
    name="极速小说阅读器-单文件版",
    version="4.0",
    description="极速小说阅读器 - 单文件版本（仅支持TXT）",
    options={"build_exe": build_exe_options},
    executables=[Executable("novel_reader.py", base="Win32GUI", target_name="极速小说阅读器-单文件版.exe")],
    # 明确指定只打包必要的文件
    include_package_data=False,
)