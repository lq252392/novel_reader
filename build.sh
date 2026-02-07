#!/bin/bash

echo "======================================"
echo "小说阅读器打包脚本 (Linux)"
echo "======================================"

echo "检查 cx_freeze 是否已安装..."
python3 -c "import cx_Freeze" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "未检测到 cx_freeze，开始安装..."
    pip install cx_freeze
    if [ $? -ne 0 ]; then
        echo "错误：cx_freeze 安装失败！"
        exit 1
    fi
    echo "cx_freeze 安装成功！"
else
    echo "cx_freeze 已安装，跳过安装步骤。"
fi

echo
echo "检查 setup.py 文件..."
if [ ! -f "setup.py" ]; then
    echo "创建 setup.py 文件..."
    cat > setup.py << 'EOF'
import sys
from cx_Freeze import setup, Executable

build_exe_options = {
    "packages": ["tkinter", "os", "sys", "re", "chardet"],
    "include_files": [],
}

setup(
    name="NovelReader",
    version="1.0",
    description="小说阅读器",
    options={"build_exe": build_exe_options},
    executables=[Executable("novel_reader.py")]
)
EOF
    echo "setup.py 创建成功！"
else
    echo "setup.py 已存在，使用现有文件。"
fi

echo
echo "开始打包..."
python3 setup.py build

if [ $? -eq 0 ]; then
    echo
    echo "======================================"
    echo "打包成功！"
    echo "可执行文件位置：build/exe.linux-x86_64-3.*/NovelReader"
    echo "======================================"
else
    echo
    echo "打包失败，请检查错误信息。"
fi

echo
