@echo off
chcp 65001 >nul
echo ============================================
echo   PyTutor - 一键安装 (Windows)
echo ============================================
echo.

cd /d "%~dp0"

:: 1. Backend .env
if not exist "backend\.env" (
    echo [1/4] 创建 backend\.env...
    copy "backend\.env.example" "backend\.env" >nul
    echo   请编辑 backend\.env 填入你的 API Key！
) else (
    echo [1/4] backend\.env 已存在，跳过
)

:: 2. Python deps
echo [2/4] 安装 Python 依赖...
cd backend
python -m venv .venv 2>nul
call .venv\Scripts\activate.bat
pip install -e . -q
cd ..

:: 3. Node deps
echo [3/4] 安装前端依赖...
cd frontend
call npm install --silent
cd ..

:: 4. Done
echo [4/4] 完成！
echo.
echo ============================================
echo   启动方式:
echo     终端1: cd backend ^&^& .venv\Scripts\activate ^&^& uvicorn app.main:app --host 0.0.0.0 --port 8000
echo     终端2: cd frontend ^&^& npm run dev
echo   然后打开: http://localhost:3000
echo ============================================
pause
