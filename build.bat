@echo off
chcp 65001 >nul

echo ======================================
echo 小说阅读器打包脚本 (Windows)
echo ======================================

echo 检查 cx_freeze 是否已安装...
python -c "import cx_Freeze" >nul 2>&1
if %errorlevel% neq 0 (
    echo 未检测到 cx_freeze，开始安装...
    pip install cx_freeze
    if %errorlevel% neq 0 (
        echo 错误：cx_freeze 安装失败！
        pause
        exit /b 1
    )
    echo cx_freeze 安装成功！
) else (
    echo cx_freeze 已安装，跳过安装步骤。
)

echo.
echo 检查 setup.py 文件...
if not exist "setup.py" (
    echo 创建 setup.py 文件...
    (
echo import sys
echo from cx_Freeze import setup, Executable
echo.
echo build_exe_options = {
echo     "packages": ["tkinter", "os", "sys", "re", "chardet"],
echo     "include_files": [],
echo }
echo.
echo setup(
echo     name="NovelReader",
echo     version="1.0",
echo     description="小说阅读器",
echo     options={"build_exe": build_exe_options},
echo     executables=[Executable("novel_reader.py", base="Win32GUI")]
echo )
) > setup.py
    echo setup.py 创建成功！
) else (
    echo setup.py 已存在，使用现有文件。
)

echo.
echo 开始打包...
python setup.py build

if %errorlevel% equ 0 (
    echo.
    echo ======================================
    echo 打包成功！
    echo 可执行文件位置：build\\exe.win-amd64-3.*\\NovelReader.exe
    echo ======================================
) else (
    echo.
    echo 打包失败，请检查错误信息。
)

echo.
pause