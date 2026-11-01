"""
代码执行服务
============

处理代码提交、执行和结果记录。
"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatSession
from app.models.exercise import Exercise
from app.models.submission import CodeSubmission, ExecutionResult
from app.models.user import User
from app.observability.logger import get_logger
from app.sandbox.runner import execute_student_code
from app.schemas.code import CodeSubmitRequest, CodeSubmitResponse, ExecutionResultResponse

logger = get_logger(__name__)


async def submit_and_execute(
    db: AsyncSession,
    user: User,
    request: CodeSubmitRequest,
    stdin_input: str = "",
) -> CodeSubmitResponse:
    """
    提交代码并执行。

    完整流程：
    1. 创建提交记录
    2. 执行代码
    3. 保存执行结果
    4. 返回响应

    参数:
        db: 数据库会话
        user: 提交者
        request: 代码提交请求

    返回:
        CodeSubmitResponse: 含执行结果
    """
    # 步骤 0：校验外键。SQLite 默认不强制外键，直接入库会留下指向不存在
    # 会话/练习的提交（甚至是别人会话里的提交），统计和回放都会错。
    if request.session_id:
        chat_session = (await db.execute(
            select(ChatSession).where(ChatSession.id == request.session_id)
        )).scalar_one_or_none()
        if chat_session is None:
            raise HTTPException(status_code=404, detail="会话不存在")
        if chat_session.student_id != user.id:
            raise HTTPException(status_code=403, detail="无权在该会话中提交代码")

    if request.exercise_id:
        exercise = (await db.execute(
            select(Exercise).where(Exercise.id == request.exercise_id)
        )).scalar_one_or_none()
        if exercise is None:
            raise HTTPException(status_code=404, detail="练习不存在")

    # 步骤 1：创建提交记录
    submission = CodeSubmission(
        user_id=user.id,
        session_id=request.session_id,
        exercise_id=request.exercise_id,
        code=request.code,
        status="running",
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    # 步骤 2：安全执行代码（统一走 runner，隔离策略由配置决定）
    exec_result = await execute_student_code(request.code, stdin_input=stdin_input or "")

    # 步骤 3：保存执行结果
    result = ExecutionResult(
        submission_id=submission.id,
        exit_code=exec_result["exit_code"],
        stdout=exec_result["stdout"],
        stderr=exec_result["stderr"],
        status=exec_result["status"],
        runtime_ms=exec_result["runtime_ms"],
        memory_kb=exec_result["memory_kb"],
        timeout_triggered=exec_result["timeout_triggered"],
    )
    db.add(result)

    # 更新提交状态
    submission.status = exec_result["status"]

    await db.commit()
    await db.refresh(result)

    logger.info(
        "code_submission_completed",
        submission_id=submission.id,
        user_id=user.id,
        status=exec_result["status"],
        runtime_ms=exec_result["runtime_ms"],
    )

    # 步骤 4：返回响应
    return CodeSubmitResponse(
        submission_id=submission.id,
        status=exec_result["status"],
        result=ExecutionResultResponse.model_validate(result),
        message=_get_result_message(exec_result),
    )


def _get_result_message(exec_result: dict) -> str:
    """根据执行状态生成用户友好的提示信息。"""
    status = exec_result["status"]
    if status == "completed":
        return "代码执行成功"
    elif status == "timeout":
        return "代码执行超时（超过 10 秒），可能包含无限循环"
    elif status == "blocked":
        return "代码被安全检查拦截"
    elif status == "error":
        if exec_result["exit_code"] != 0:
            return f"代码执行出错（退出码: {exec_result['exit_code']}）"
        return "代码执行出错"
    return "未知状态"
