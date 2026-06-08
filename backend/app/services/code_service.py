"""
代码执行服务
============

处理代码提交、执行和结果记录。
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.submission import CodeSubmission, ExecutionResult
from app.models.user import User
from app.observability.logger import get_logger
from app.sandbox.executor import execute_python_code
from app.schemas.code import CodeSubmitRequest, CodeSubmitResponse, ExecutionResultResponse

logger = get_logger(__name__)


async def submit_and_execute(
    db: AsyncSession,
    user: User,
    request: CodeSubmitRequest,
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

    # 步骤 2：安全执行代码
    exec_result = await execute_python_code(request.code)

    # 步骤 2.5：错误分析（有 stderr 时用 LLM 解释错误原因）
    error_analysis = None
    if exec_result["stderr"] and exec_result["status"] not in ("completed",):
        try:
            from app.schemas.ai import ChatMessage as LLMMessage
            from app.services.llm_service import chat_completion
            analysis_prompt = (
                f"学生写了以下 Python 代码：\n```python\n{request.code[:500]}\n```\n\n"
                f"执行后报错：\n{exec_result['stderr'][:300]}\n\n"
                f"请用 2-3 句话用中文简要解释：1) 错误原因 2) 如何修复。"
                f"同时在回复末尾用一行 <!-- concepts:xxx,yyy --> 标注涉及的知识点。"
            )
            llm_resp = await chat_completion(
                messages=[LLMMessage(role="user", content=analysis_prompt)],
                temperature=0.3, max_tokens=300,
            )
            raw = llm_resp.content.strip()
            import re
            concepts = []
            meta = re.search(r'<!--\s*concepts:(.+?)\s*-->', raw)
            if meta:
                concepts = [c.strip() for c in meta.group(1).split(",") if c.strip()]
                raw = raw[:meta.start()].strip()
            error_analysis = {"explanation": raw, "concepts": concepts}
        except Exception:
            pass

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
    from app.schemas.code import ErrorAnalysis
    return CodeSubmitResponse(
        submission_id=submission.id,
        status=exec_result["status"],
        result=ExecutionResultResponse.model_validate(result),
        message=error_analysis["explanation"] if error_analysis else _get_result_message(exec_result),
        error_analysis=ErrorAnalysis(**error_analysis) if error_analysis else None,
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
