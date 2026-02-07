@echo off
chcp 437 >nul
setlocal enabledelayedexpansion

echo ======================================
echo Novel Reader Packaging Script (Windows)
echo ======================================

echo Checking if cx_freeze is installed...
python -c "import cx_Freeze" >nul 2>&1
if errorlevel 1 (
    echo cx_Freeze not detected, installing...
    python -m pip install cx_freeze
    if errorlevel 1 (
        echo Error: cx_freeze installation failed!
        pause
        exit /b 1
    )
    echo cx_freeze installed successfully!
) else (
    echo cx_freeze already installed, skipping installation.
)

echo.
echo Cleaning old build directory...
if exist "build" (
    rmdir /s /q "build"
    echo Old build directory cleaned.
)

echo.
echo Starting packaging...
python setup.py build

if not errorlevel 1 (
    echo.
    echo ======================================
    echo Packaging successful!
    echo ======================================

    echo Searching for build directory...
    set "BUILD_DIR="
    for /d %%i in (build\exe.*) do (
        set "BUILD_DIR=%%i"
        goto :found_build
    )
    
    :found_build
    if defined BUILD_DIR (
        echo Found build directory: !BUILD_DIR!

        echo Getting build directory name...
        for %%f in ("!BUILD_DIR!") do set "DIR_NAME=%%~nxf"

        echo Creating archive...
        powershell -Command "Compress-Archive -Path '!BUILD_DIR!' -DestinationPath 'NovelReader-!DIR_NAME!.zip' -Force"
        if not errorlevel 1 (
            echo.
            echo ======================================
            echo Compression successful!
            echo Archive location: NovelReader-!DIR_NAME!.zip
            echo ======================================
        ) else (
            echo PowerShell compression failed!
            echo Trying 7-Zip compression...

            REM Try 7-Zip if PowerShell fails
            if exist "C:\Program Files\7-Zip\7z.exe" (
                "C:\Program Files\7-Zip\7z.exe" a -tzip "NovelReader-!DIR_NAME!.zip" "!BUILD_DIR!"
                if not errorlevel 1 (
                    echo.
                    echo ======================================
                    echo 7-Zip compression successful!
                    echo Archive location: NovelReader-!DIR_NAME!.zip
                    echo ======================================
                ) else (
                    echo 7-Zip compression also failed!
                    echo Build directory located at: !BUILD_DIR!
                )
            ) else (
                echo Neither PowerShell nor 7-Zip found, skipping compression.
                echo Build directory located at: !BUILD_DIR!
            )
        )
    ) else (
        echo Build directory not found!
    )
    goto :after_found_build
) else (
    echo.
    echo Packaging failed, please check error messages.
)

:after_found_build
echo.
pause