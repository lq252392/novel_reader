@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ========================
echo 极速小说阅读器打包工具
echo ========================
echo.
echo 请选择打包版本：
echo 1. 模块化版本（支持扩展格式）
echo 2. 单文件版本（仅TXT支持）
echo 3. 两个版本都打包
echo.
set /p choice=请输入选择 (1/2/3): 

REM 检查是否安装了 cx_Freeze
python -c "import cx_Freeze" >nul 2>&1
if errorlevel 1 (
    echo.
    echo 正在安装 cx_Freeze...
    pip install cx_Freeze
    if errorlevel 1 (
        echo 错误：无法安装 cx_Freeze，请手动安装后再试
        pause
        exit /b 1
    )
)

if "%choice%"=="1" (
    goto build_modular
) else if "%choice%"=="2" (
    goto build_single
) else if "%choice%"=="3" (
    goto build_both
) else (
    echo 无效的选择，请重新运行脚本
    pause
    exit /b 1
)

:build_modular
echo.
echo 开始打包模块化版本...
rmdir /s /q build 2>nul
python setup.py build
if errorlevel 1 (
    echo 模块化版本打包失败
    pause
    exit /b 1
)
echo.
echo 模块化版本打包完成！
echo 可执行文件位于 build/极速小说阅读器 目录
goto zip_modular

:build_single
echo.
echo 开始打包单文件版本...
rmdir /s /q build 2>nul
python setup_single.py build
if errorlevel 1 (
    echo 单文件版本打包失败
    pause
    exit /b 1
)
echo.
echo 单文件版本打包完成！
echo 可执行文件位于 build/极速小说阅读器-单文件版 目录
goto zip_single

:build_both
echo.
echo 开始打包两个版本...

REM 打包模块化版本
rmdir /s /q build 2>nul
python setup.py build
if errorlevel 1 (
    echo 模块化版本打包失败
    pause
    exit /b 1
)

REM 重命名构建目录
if exist "build\极速小说阅读器" (
    move "build\极速小说阅读器" "build\temp_modular" 2>nul
)

REM 打包单文件版本
python setup_single.py build
if errorlevel 1 (
    echo 单文件版本打包失败
    pause
    exit /b 1
)

REM 移动单文件版本到临时目录
if exist "build\极速小说阅读器-单文件版" (
    move "build\极速小说阅读器-单文件版" "build\temp_single" 2>nul
)

REM 恢复目录结构
move "build\temp_modular" "build\极速小说阅读器" 2>nul
move "build\temp_single" "build\极速小说阅读器-单文件版" 2>nul

echo.
echo 两个版本打包完成！
echo 模块化版本位于 build/极速小说阅读器 目录
echo 单文件版本位于 build/极速小说阅读器-单文件版 目录
goto zip_both

:zip_modular
REM 压缩模块化版本
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-3 delims=: " %%a in ('time /t') do (set mytime=%%a%%b%%c)
set mytime=!mytime: =0!
set zipfile=NovelReader-modular-!mydate!-!mytime!.zip

cd build
if exist "极速小说阅读器" (
    powershell -ExecutionPolicy Bypass -Command "Compress-Archive -Path '极速小说阅读器' -DestinationPath '..\!zipfile!' -Force"
    cd ..
    echo 已压缩为 !zipfile!
) else (
    cd ..
)
goto end

:zip_single
REM 压缩单文件版本
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-3 delims=: " %%a in ('time /t') do (set mytime=%%a%%b%%c)
set mytime=!mytime: =0!
set zipfile=NovelReader-single-!mydate!-!mytime!.zip

cd build
if exist "极速小说阅读器-单文件版" (
    powershell -ExecutionPolicy Bypass -Command "Compress-Archive -Path '极速小说阅读器-单文件版' -DestinationPath '..\!zipfile!' -Force"
    cd ..
    echo 已压缩为 !zipfile!
) else (
    cd ..
)
goto end

:zip_both
REM 压缩两个版本
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-3 delims=: " %%a in ('time /t') do (set mytime=%%a%%b%%c)
set mytime=!mytime: =0!
set zipfile=NovelReader-all-!mydate!-!mytime!.zip

cd build
powershell -ExecutionPolicy Bypass -Command "Compress-Archive -Path '极速小说阅读器', '极速小说阅读器-单文件版' -DestinationPath '..\!zipfile!' -Force"
cd ..
echo 已压缩为 !zipfile!

:end
echo.
echo 打包完成！
pause