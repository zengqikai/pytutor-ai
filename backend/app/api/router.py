"""
主路由聚合器
============

将所有 v1 子路由汇总到一个主路由器，main.py 中只需一行 include_router。
添加新模块时只需 import + include_router 两行。
"""

from fastapi import APIRouter

from app.api.v1.admin import router as admin_router
from app.api.v1.agent import router as agent_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.code import router as code_router
from app.api.v1.exercises import router as exercises_router
from app.api.v1.misconception_exercises import router as mc_exercises_router
from app.api.v1.misconceptions import router as misconceptions_router
from app.api.v1.profile import router as profile_router
from app.api.v1.rag import router as rag_router
from app.api.v1.teacher import router as teacher_router
from app.api.v1.users import router as users_router

# v1 主路由器，prefix="/api/v1" 在 main.py 中设置
api_v1_router = APIRouter()

# 按功能模块注册子路由
api_v1_router.include_router(auth_router,          prefix="/auth",          tags=["认证"])
api_v1_router.include_router(users_router,         prefix="/users",         tags=["用户"])
api_v1_router.include_router(chat_router,          prefix="/chat",          tags=["聊天"])
api_v1_router.include_router(rag_router,           prefix="/rag",           tags=["知识库"])
api_v1_router.include_router(code_router,          prefix="/code",          tags=["代码"])
api_v1_router.include_router(agent_router,         prefix="/agent",         tags=["Agent"])
api_v1_router.include_router(exercises_router,     prefix="/exercises",     tags=["练习"])
api_v1_router.include_router(mc_exercises_router,  prefix="/exercises",     tags=["练习"])
api_v1_router.include_router(misconceptions_router,prefix="/misconceptions",tags=["误区诊断"])
api_v1_router.include_router(profile_router,       prefix="/profile",       tags=["画像"])
api_v1_router.include_router(teacher_router,       prefix="/teacher",       tags=["教师"])
api_v1_router.include_router(admin_router,         prefix="/admin",         tags=["管理"])
