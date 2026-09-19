@echo off
REM ============================================================
REM  MC Bridge Tool - Windows 打包脚本
REM  产物：dist\MC Bridge Tool\  （onedir）
REM        dist\MC Bridge Tool.exe （如改 spec 里 ONEFILE=True）
REM ============================================================

setlocal

echo [mcbridge] 切换到仓库根目录...
cd /d "%~dp0\.."

REM ---- 检查 Python ----
where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未找到 python，请先安装 Python 3.10+ 并加入 PATH。
    pause
    exit /b 1
)

echo [mcbridge] 当前 Python 版本：
python --version

REM ---- 32 位提示 ----
python -c "import struct,sys; print('ARCH=' + ('32bit' if struct.calcsize(\"P\")==4 else '64bit'))" | findstr "32bit" >nul
if not errorlevel 1 (
    echo [提示] 当前是 32 位 Python 环境，适合打 32 位 Windows 包。
    echo        注意：Python 3.11+ 已不支持 32 位 Windows，打 32 位包必须用 Python 3.10 32 位。
)

REM ---- 装依赖 ----
echo [mcbridge] 安装依赖...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

REM ---- 清理旧产物 ----
echo [mcbridge] 清理 build/ dist/ ...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM ---- 打包 ----
echo [mcbridge] 开始 PyInstaller 打包...
python -m PyInstaller packaging\mcbridge.spec --noconfirm

if errorlevel 1 (
    echo [错误] 打包失败，请查看上面的日志。
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  打包完成！
echo  产物目录：dist\MC Bridge Tool\
echo  双击 dist\MC Bridge Tool\MC Bridge Tool.exe 即可运行。
echo ============================================================
echo.
pause
endlocal
