"""
应用配置模块
============

使用 pydantic-settings 从 .env 文件和环境变量中加载配置。

原理说明：
---------
pydantic-settings 是 pydantic 的扩展，专门用于管理应用配置。
它会按照以下优先级读取配置（后面的覆盖前面的）：
1. 代码中定义的默认值
2. .env 文件中的值
3. 操作系统环境变量中的值

这样做的好处：
- 开发和测试时用 .env 文件，方便本地调试
- 生产部署时用 K8s ConfigMap/Secret 注入环境变量
- 敏感信息（密码、Key）永远不写进代码
"""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# 项目根目录的绝对路径（backend/ 目录）
# Path(__file__).resolve() 获取当前文件的绝对路径
# .parent.parent 向上两级：config.py -> core -> app -> backend/
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    应用配置类

    每个属性对应一个配置项。pydantic-settings 会自动从 .env 文件和
    环境变量中查找同名（不区分大小写）的值。

    例如：
    - 属性 app_name 会匹配 .env 中的 APP_NAME
    - 属性 deepseek_api_key 会匹配 .env 中的 DEEPSEEK_API_KEY
    """

    # ==============================
    # 应用基础配置
    # ==============================
    app_name: str = Field(
        default="AI Python Tutor",
        description="应用名称，用于 Swagger 文档标题和日志标识"
    )
    app_env: str = Field(
        default="development",
        description="运行环境：development | testing | staging | production"
    )
    debug: bool = Field(
        default=True,
        description="调试模式：True 时显示详细错误信息，生产环境必须设为 False"
    )
    secret_key: str = Field(
        default="change-me-to-a-random-string",
        description="JWT 签名密钥。生产环境必须使用强随机字符串！"
    )

    # ==============================
    # 服务器配置
    # ==============================
    host: str = Field(
        default="0.0.0.0",
        description="服务器监听地址。0.0.0.0 表示接受所有网络接口的连接"
    )
    port: int = Field(
        default=8000,
        description="服务器监听端口"
    )

    # ==============================
    # CORS 配置（跨域资源共享）
    # ==============================
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        description="允许访问后端的前端地址列表，逗号分隔"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """将逗号分隔的字符串转为 Python 列表，方便 FastAPI 使用"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    # ==============================
    # 数据库配置
    # ==============================
    database_url: str = Field(
        default="sqlite+aiosqlite:///./ai_tutor.db",
        description=(
            "数据库连接 URL。\n"
            "开发环境：sqlite+aiosqlite:///./ai_tutor.db（文件存储，无需安装数据库）\n"
            "生产环境：postgresql+asyncpg://user:password@host:5432/dbname"
        )
    )

    @property
    def is_sqlite(self) -> bool:
        """判断当前是否使用 SQLite 数据库（开发环境）"""
        return self.database_url.startswith("sqlite")

    # ==============================
    # DeepSeek AI 配置
    # ==============================
    deepseek_api_key: str = Field(
        default="sk-placeholder",
        description="DeepSeek API Key，从 https://platform.deepseek.com 获取"
    )
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        description="DeepSeek API 地址（OpenAI 兼容接口）"
    )
    deepseek_model: str = Field(
        default="deepseek-chat",
        description="默认使用的 DeepSeek 模型"
    )
    deepseek_fallback_model: Optional[str] = Field(
        default=None,
        description="备用模型。主模型不可用时自动切换。"
    )

    # ==============================
    # LLM 通用参数
    # ==============================
    llm_temperature: float = Field(
        default=0.7,
        ge=0.0,   # 大于等于 0
        le=2.0,   # 小于等于 2
        description="LLM 生成温度。0=确定性强（适合代码），1=创造性高（适合对话）"
    )
    llm_max_tokens: int = Field(
        default=4096,
        ge=1,
        description="LLM 单次回复最大 token 数"
    )
    llm_timeout: int = Field(
        default=60,
        ge=1,
        description="LLM API 调用超时时间（秒）"
    )

    # ==============================
    # 日志配置
    # ==============================
    log_level: str = Field(
        default="DEBUG",
        description="日志级别：DEBUG | INFO | WARNING | ERROR。开发用 DEBUG，生产用 INFO"
    )
    log_format: str = Field(
        default="console",
        description="日志格式：console（彩色可读）| json（结构化，适合日志收集系统）"
    )

    # ==============================
    # pydantic-settings 配置
    # ==============================
    model_config = SettingsConfigDict(
        # .env 文件的路径
        env_file=".env",
        # 如果 .env 文件不存在不报错（Docker 部署时可能只用环境变量）
        env_file_encoding="utf-8",
        # 不区分大小写匹配环境变量
        case_sensitive=False,
        # 额外的环境变量前缀（可选，例如所有变量都以 TUTOR_ 开头）
        # env_prefix="TUTOR_",
    )


# =============================================================================
# 全局单例
# =============================================================================
# 创建全局唯一的配置实例。
# 整个应用中的所有模块都 import 这个实例，保证配置一致性。
#
# 注意：创建实例时会立即读取 .env 文件和环境变量，
# 如果 .env 不存在或格式错误，这里会抛出异常。
# =============================================================================
settings = Settings()
