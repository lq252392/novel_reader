import sys
from cx_Freeze import setup, Executable

build_exe_options = {
    "packages": ["tkinter", "os", "sys"],
    "include_files": [],
}

setup(
    name="NovelReader",
    version="1.0",
    description="小说阅读器",
    options={"build_exe": build_exe_options},
    executables=[Executable("novel_reader.py", base="Win32GUI")]
)