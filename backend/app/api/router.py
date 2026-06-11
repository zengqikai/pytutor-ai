"""
主路由聚合器
===========

把所有 v1 模块的子路由汇总到一个主路由器中。
然后在 main.py 中只需一行 include_router 即可注册所有路由。

这样做的好处：
- 每个功能模块（auth、users、chat...）的路由独立管理
- 测试时可以选择性加载特定模块
- 添加新模块只需在 router.py 中加一行
"""

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.agent import router as agent_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.code import router as code_router
from app.api.v1.exercises import router as exercises_router
from app.api.v1.profile import router as profile_router
from app.api.v1.rag import router as rag_router
from app.api.v1.misconceptions import router as misconceptions_router
from app.api.v1.users import router as users_router

# 创建 v1 主路由器
# prefix="/api/v1" 已添加到 main.py 的 include_router 中
api_v1_router = APIRouter()

# 注册子路由模块
api_v1_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_v1_router.include_router(users_router, prefix="/users", tags=["用户"])
api_v1_router.include_router(chat_router, prefix="/chat", tags=["聊天"])
api_v1_router.include_router(rag_router, prefix="/rag", tags=["知识库"])
api_v1_router.include_router(code_router, prefix="/code", tags=["代码"])
api_v1_router.include_router(agent_router, prefix="/agent", tags=["Agent"])
api_v1_router.include_router(exercises_router, prefix="/exercises", tags=["练习"])
api_v1_router.include_router(profile_router, prefix="/profile", tags=["画像"])
api_v1_router.include_router(misconceptions_router, prefix="/misconceptions", tags=["误区诊断"])
api_v1_router.include_router(admin_router, prefix="/admin", tags=["管理"])
