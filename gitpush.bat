@echo off
chcp 65001 >nul

:: 检查是否在Git仓库目录
git rev-parse --is-inside-work-tree >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误：当前目录不是Git仓库！
    pause
    exit /b 1
)

:: 获取commit message（优先使用命令行参数）
set msg=%~1

:: 如果没有提供参数，则提示用户输入
if "%msg%"=="" (
    set /p msg="请输入Commit Message: "
    if "%msg%"=="" (
        echo 错误：Commit Message不能为空！
        pause
        exit /b 1
    )
)

echo.
echo 开始Git提交流程...
echo.

:: 执行Git命令
git add . && git commit -m "%msg%" && git push -u origin master

:: 检查执行结果
if %errorlevel% equ 0 (
    echo.
    echo Git提交成功！
    echo Commit Message: %msg%
) else (
    echo.
    echo Git提交失败！
)

echo.
pause