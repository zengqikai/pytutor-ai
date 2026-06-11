#!/bin/bash
set -e
echo "============================================"
echo "  PyTutor - 一键安装 (Linux/Mac)"
echo "============================================"

cd "$(dirname "$0")"

# 1. Backend .env
if [ ! -f "backend/.env" ]; then
    echo "[1/4] 创建 backend/.env..."
    cp backend/.env.example backend/.env
    echo "  请编辑 backend/.env 填入你的 API Key！"
else
    echo "[1/4] backend/.env 已存在，跳过"
fi

# 2. Python deps
echo "[2/4] 安装 Python 依赖..."
cd backend
python3 -m venv .venv 2>/dev/null || python -m venv .venv
source .venv/bin/activate
pip install -e . -q
cd ..

# 3. Node deps
echo "[3/4] 安装前端依赖..."
cd frontend
npm install --silent
cd ..

# 4. Done
echo "[4/4] 完成！"
echo ""
echo "============================================"
echo "  启动方式:"
echo "    终端1: cd backend && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo "    终端2: cd frontend && npm run dev"
echo "  然后打开: http://localhost:3000"
echo "============================================"
