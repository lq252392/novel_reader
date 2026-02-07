import sys
from cx_Freeze import setup, Executable

build_exe_options = {
    "packages": ["tkinter", "os", "sys", "json", "re", "threading", "time"],
    "excludes": ["tkinter.test", "tkinter.tests"],
    "include_files": [],
    "optimize": 2,
}

setup(
    name="NovelReader",
    version="1.0",
    description="小说阅读器",
    options={"build_exe": build_exe_options},
    executables=[Executable("novel_reader.py", base="Win32GUI", target_name="NovelReader.exe")]
)