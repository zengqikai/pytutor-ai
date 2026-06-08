# =============================================================================
# AI Python Tutor - 常用命令
# =============================================================================
# 用法: make <目标>
# 例如: make dev     # 启动开发服务器

.PHONY: help dev install migrate test clean docker-up docker-down

help:  ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ==============================
# 开发
# ==============================
dev:  ## 启动开发服务器（热重载）
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

install:  ## 安装项目依赖
	cd backend && pip install -e ".[dev,test]"

# ==============================
# 数据库
# ==============================
migrate:  ## 运行数据库迁移
	cd backend && alembic upgrade head

migration:  ## 生成新的迁移文件（用法: make migration msg="描述"）
	cd backend && alembic revision --autogenerate -m "$(msg)"

rollback:  ## 回滚最后一次迁移
	cd backend && alembic downgrade -1

# ==============================
# 测试
# ==============================
test:  ## 运行所有测试
	cd backend && pytest -v

test-cov:  ## 运行测试并生成覆盖率报告
	cd backend && pytest --cov=app --cov-report=html

# ==============================
# Docker
# ==============================
docker-up:  ## 启动 Docker Compose 环境
	docker-compose up -d

docker-down:  ## 停止 Docker Compose 环境
	docker-compose down

docker-build:  ## 构建 Docker 镜像
	docker-compose build

docker-logs:  ## 查看 Docker 日志
	docker-compose logs -f

# ==============================
# 清理
# ==============================
clean:  ## 清理临时文件
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/.venv
