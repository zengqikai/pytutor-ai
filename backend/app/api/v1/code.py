"""
代码执行 API
============

接口列表：
    POST /api/v1/code/submit - 提交并执行代码
    GET  /api/v1/code/submissions/{id} - 获取提交详情
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.session import get_db
from app.models.submission import CodeSubmission
from app.models.user import User
from app.schemas.code import CodeSubmitRequest, CodeSubmitResponse
from app.security.dependencies import get_current_user
from app.services.code_service import submit_and_execute

router = APIRouter()


@router.post("/submit", response_model=CodeSubmitResponse)
async def submit_code(
    request: CodeSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    提交 Python 代码并在沙箱中执行。

    安全措施：
    - 禁止导入 os、subprocess、sys 等危险模块
    - 执行超时 10 秒
    - 输出限制 100KB

    请求示例:
        {
            "code": "print('Hello, World!')\\nfor i in range(5):\\n    print(i)",
            "exercise_id": null,
            "session_id": "uuid-of-chat-session"
        }

    响应示例:
        {
            "submission_id": "uuid",
            "status": "completed",
            "result": {
                "stdout": "Hello, World!\\n0\\n1\\n2\\n3\\n4\\n",
                "stderr": "",
                "exit_code": 0,
                "runtime_ms": 45.2
            }
        }
    """
    return await submit_and_execute(db, current_user, request, request.stdin)


@router.post("/analyze")
async def analyze_error(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """独立错误分析接口——不影响代码执行速度。"""
    code = body.get("code", "")
    stderr = body.get("stderr", "")

    if not stderr.strip():
        return {"explanation": "", "concepts": []}

    from app.schemas.ai import ChatMessage as LLMMessage
    from app.services.llm_service import chat_completion

    prompt = (
        f"学生写了以下 Python 代码：\n```python\n{code[:500]}\n```\n\n"
        f"执行后报错：\n{stderr[:300]}\n\n"
        f"请用 2-3 句话用中文简要解释：1) 错误原因 2) 如何修复。"
        f"同时在回复末尾用一行 <!-- concepts:xxx,yyy --> 标注涉及的知识点。"
    )

    try:
        llm_resp = await chat_completion(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.3, max_tokens=300,
        )
        raw = llm_resp.content.strip()
        concepts = []
        import re
        meta = re.search(r'<!--\s*concepts:(.+?)\s*-->', raw)
        if meta:
            concepts = [c.strip() for c in meta.group(1).split(",") if c.strip()]
            raw = raw[:meta.start()].strip()
        return {"explanation": raw, "concepts": concepts}
    except Exception as e:
        return {"explanation": f"分析失败: {str(e)[:100]}", "concepts": []}


@router.get("/submissions/{submission_id}")
async def get_submission(
    submission_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取代码提交详情（含执行结果）。"""
    result = await db.execute(
        select(CodeSubmission)
        .where(CodeSubmission.id == submission_id)
    )
    submission = result.scalar_one_or_none()

    if not submission:
        return {"detail": "提交记录不存在"}

    # 权限检查
    if current_user.role == "student" and submission.user_id != current_user.id:
        return {"detail": "无权访问"}

    return {
        "id": submission.id,
        "code": submission.code,
        "status": submission.status,
        "language": submission.language,
        "created_at": submission.created_at.isoformat(),
    }
