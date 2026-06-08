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
    return await submit_and_execute(db, current_user, request)


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
