# =============================================================================
# AI Python Tutor Backend Dockerfile
# =============================================================================
# 使用多阶段构建（Multi-stage Build）减小镜像体积。
#
# 阶段 1（builder）：安装依赖 → 只有 poetry/pip 工具
# 阶段 2（runtime）：复制依赖 + 代码 → 最终运行镜像，不含编译工具
#
# 为什么要多阶段？
# - 最终镜像不包含 gcc、git 等编译工具（减小攻击面 + 体积）
# - pip 安装的包在 builder 阶段编译好，runtime 阶段只复制结果
# =============================================================================

# ---- 阶段 1：依赖构建 ----
FROM python:3.12-slim AS builder

# 设置工作目录
WORKDIR /app

# 安装系统依赖（编译 python 包可能需要的库）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖声明文件
COPY pyproject.toml ./

# 安装 Python 依赖到临时目录
# --no-cache-dir: 不缓存下载的包，减小镜像体积
# --prefix=/install: 安装到 /install 目录而非系统目录
RUN pip install --no-cache-dir --prefix=/install .


# ---- 阶段 2：运行时 ----
FROM python:3.12-slim AS runtime

# 避免 Python 生成 .pyc 文件
ENV PYTHONDONTWRITEBYTECODE=1
# 关闭输出缓冲（日志立即显示，不缓冲）
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 从 builder 阶段复制已安装的依赖
COPY --from=builder /install /usr/local

# 复制应用代码
COPY . .

# 创建非 root 用户（安全最佳实践）
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# 声明容器监听端口（文档作用，实际端口在启动命令中指定）
EXPOSE 8000

# 健康检查
# 每 30 秒检查一次，超时 5 秒，连续失败 3 次标记为 unhealthy
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

# 启动命令
# 格式：uvicorn <模块路径>:<变量名> --host <绑定地址> --port <端口>
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
