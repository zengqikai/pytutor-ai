"""
练习 API
========

接口：
    POST   /api/v1/exercises/generate - AI 生成练习
    GET    /api/v1/exercises          - 练习列表
    GET    /api/v1/exercises/{id}     - 练习详情
    POST   /api/v1/exercises/{id}/submit - 提交答案（执行测试用例）
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.exercise import Exercise
from app.models.user import User, UserRole
from app.sandbox.executor import execute_python_code
from app.schemas.exercise import ExerciseGenerateRequest, ExerciseResponse
from app.security.dependencies import get_current_user, require_role
from app.services.exercise_service import generate_exercises, get_exercise, list_exercises

router = APIRouter()


@router.get("", response_model=list[ExerciseResponse])
async def list_exercise_list(
    difficulty: int | None = Query(default=None, ge=1, le=5),
    concepts: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取练习题列表（可按难度和知识点筛选）。"""
    return await list_exercises(db, difficulty=difficulty, concepts=concepts, limit=limit, offset=offset)


@router.post("/generate")
async def generate_exercise_list(
    request: ExerciseGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 生成个性化练习题。"""
    exercises = await generate_exercises(db, request)
    return {"exercises": exercises, "count": len(exercises)}


@router.post("/{exercise_id}/hint")
async def get_exercise_hint(
    exercise_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取分层提示。hint_level: 1-5（前端累积请求递增）。"""
    from sqlalchemy import select
    from app.schemas.ai import ChatMessage as LLMMessage
    from app.services.llm_service import chat_completion

    r = await db.execute(select(Exercise).where(Exercise.id == exercise_id))
    exercise = r.scalar_one_or_none()
    if not exercise:
        return {"detail": "练习不存在"}

    level = body.get("hint_level", 1)
    user_code = body.get("code", "")
    failed_info = body.get("failed_info", "")

    hint_prompts = {
        1: f"学生正在做一道题：{exercise.title}。请给一个概念性提示，不要涉及代码细节。",
        2: f"学生正在做一道题：{exercise.title}。请给一个更具体的方向性提示。{failed_info}",
        3: f"学生正在做一道题：{exercise.title}。请指出可能的错误方向。{failed_info}。学生当前代码：\n```python\n{user_code[:500]}\n```",
        4: f"学生正在做一道题：{exercise.title}。请给出关键代码思路。题目：{exercise.description[:500]}",
        5: f"学生正在做一道题：{exercise.title}。请给出接近完整的解题步骤。题目：{exercise.description[:500]}",
    }

    prompt = hint_prompts.get(min(level, 5), hint_prompts[1])
    prompt += "\n\n用 2-4 句中文回复，不要直接给完整代码。引导思考。"

    try:
        llm_resp = await chat_completion(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.5, max_tokens=300,
        )
        return {"hint": llm_resp.content.strip(), "hint_level": level}
    except Exception as e:
        return {"hint": f"提示生成失败: {str(e)[:100]}", "hint_level": level}


@router.get("/{exercise_id}/solution")
async def get_exercise_solution(
    exercise_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取参考答案（练习通过后或多次尝试后）。"""
    from sqlalchemy import select
    r = await db.execute(select(Exercise).where(Exercise.id == exercise_id))
    exercise = r.scalar_one_or_none()
    if not exercise:
        return {"detail": "练习不存在"}
    return {"solution": exercise.reference_solution or "暂无参考答案"}


@router.get("/{exercise_id}")
async def get_exercise_detail(
    exercise_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取练习详情。教师可见参考答案。"""
    is_teacher = current_user.role in (UserRole.INSTRUCTOR, UserRole.ADMIN)
    exercise = await get_exercise(db, exercise_id, include_solution=is_teacher)
    if not exercise:
        return {"detail": "练习不存在"}
    return exercise


@router.post("/{exercise_id}/submit")
async def submit_exercise_answer(
    exercise_id: str,
    code: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    提交练习答案，自动运行测试用例。

    请求体：{"code": "学生的 Python 代码"}
    返回：测试用例通过情况 + 执行结果
    """
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select

    # 获取练习和测试用例
    result = await db.execute(
        select(Exercise)
        .where(Exercise.id == exercise_id)
        .options(selectinload(Exercise.test_cases))
    )
    exercise = result.scalar_one_or_none()
    if not exercise:
        return {"detail": "练习不存在"}

    user_code = code.get("code", "")

    # ACM 模式：每个测试用例独立执行，stdin 传入 input_data
    from app.sandbox.executor import execute_python_code_with_input

    test_results = []
    passed = 0
    total = 0
    total_time = 0.0
    any_error = None

    for tc in sorted(exercise.test_cases, key=lambda t: t.order_index):
        total += 1
        exec_result = await execute_python_code_with_input(user_code, stdin_input=tc.input_data or "")
        total_time += exec_result.get("runtime_ms", 0)

        if exec_result["status"] == "blocked":
            test_results.append({"description": tc.description, "passed": False, "is_hidden": tc.is_hidden, "error": f"安全拦截: {exec_result['stderr']}"})
            any_error = exec_result["stderr"]
            continue
        if exec_result["status"] == "timeout":
            test_results.append({"description": tc.description, "passed": False, "is_hidden": tc.is_hidden, "error": "超时"})
            any_error = "超时"
            continue
        if exec_result["status"] == "error" and exec_result["stderr"]:
            test_results.append({"description": tc.description, "passed": False, "is_hidden": tc.is_hidden, "error": exec_result["stderr"][:200]})
            any_error = exec_result["stderr"]
            continue

        user_output = exec_result["stdout"].rstrip()
        expected = (tc.expected_output or "").rstrip()
        if user_output == expected:
            passed += 1
            test_results.append({"description": tc.description, "passed": True, "is_hidden": tc.is_hidden})
        else:
            test_results.append({"description": tc.description, "passed": False, "is_hidden": tc.is_hidden,
                "expected": expected if not tc.is_hidden else "(隐藏)",
                "got": user_output[:200] if not tc.is_hidden else "(隐藏)"})

    exercise.use_count = (exercise.use_count or 0) + 1

    # 联动学习画像：记录事件 + 更新薄弱点 + 独立完成度评分
    from app.services.profile_service import record_event, update_weakness, get_or_create_profile
    all_passed = passed == total and total > 0

    # 独立完成度评分（前端传入 used_hints 和 viewed_solution）
    used_hints = code.get("used_hints", 0)
    viewed_solution = code.get("viewed_solution", False)

    if all_passed:
        if viewed_solution:
            score_pct = 0    # 看了答案 → 不算通过
        elif used_hints >= 2:
            score_pct = 50   # 用了 2 次提示 → 50%
        elif used_hints == 1:
            score_pct = 75   # 用了 1 次提示 → 75%
        else:
            score_pct = 100  # 完全独立 → 100%
    else:
        score_pct = 0        # 未通过 → 0%
        # 未通过时仍记录尝试次数

    # 去重检查——必须在 record_event 之前！
    from app.models.profile import LearningEvent
    from sqlalchemy import select, func as _sa_func
    already_passed = (await db.execute(
        select(_sa_func.count()).select_from(LearningEvent)
        .where(LearningEvent.user_id == current_user.id, LearningEvent.event_type == "exercise_passed",
               LearningEvent.concept == (exercise.concepts.split(",")[0].strip() if exercise.concepts else exercise.title))
    )).scalar() or 0

    # 首次通过才创建 exercise_passed 事件
    await record_event(db, current_user.id,
        "exercise_passed" if (all_passed and already_passed == 0) else ("exercise_failed" if not all_passed else "exercise_retry"),
        concept=(exercise.concepts.split(",")[0] if exercise.concepts else exercise.title),
        detail={
            "title": exercise.title,
            "exercise_id": exercise.id,
            "score_pct": score_pct if already_passed == 0 else 0,
            "used_hints": used_hints,
            "viewed_solution": viewed_solution
        })
    profile = await get_or_create_profile(db, current_user.id)
    exp_gained = round(exercise.difficulty * score_pct)

    if all_passed and score_pct > 0:
        if already_passed == 0:  # 首次通过才计数
            profile.total_exercises_completed += 1
            profile.total_exercises_passed += 1
            if used_hints > 0:
                profile.total_hints_used += used_hints
    elif not all_passed:
        profile.total_exercises_completed += 1
        profile.total_exercises_completed += 1

    # 累积经验 + 升级（每 300 经验升一级，最低 Lv1）
    import json
    mastery = {}
    if profile.concept_mastery_json:
        try: mastery = json.loads(profile.concept_mastery_json)
        except: pass
    # 更新经验值
    total_exp = mastery.get("_total_exp", 0) + exp_gained
    mastery["_total_exp"] = total_exp
    profile.level = max(1, total_exp // 300 + 1)
    # 更新知识点掌握度（通过练习的知识点 +score_pct/100）
    if exercise.concepts and score_pct > 0:
        for c in exercise.concepts.split(","):
            c = c.strip()
            old = mastery.get(c, 0)
            mastery[c] = min(1.0, old + score_pct / 200)  # 每次最多加 0.5
    profile.concept_mastery_json = json.dumps(mastery, ensure_ascii=False)

    # 更新薄弱点：失败的用例对应的知识点
    if not all_passed and exercise.concepts:
        for concept in exercise.concepts.split(","):
            await update_weakness(db, current_user.id, concept.strip())

    await db.commit()
    avg_time = round(total_time / total, 2) if total > 0 else 0

    return {
        "exercise_id": exercise_id,
        "execution": {"status": "completed" if any_error is None else "error", "stderr": any_error or "", "runtime_ms": avg_time},
        "test_results": {"passed": passed, "total": total, "details": test_results, "all_passed": passed == total and total > 0},
        # 附上错因分析和提示（前端可据此展示帮助按钮）
        "help_available": passed < total,
        "score_pct": score_pct,
        "score_label": "⭐ 完全独立完成！" if score_pct == 100 else
                       "🌟 提示帮助完成" if score_pct >= 50 else
                       "📖 参考答案辅助（不计分）" if viewed_solution else
                       "❌ 未通过" if not all_passed else "",
        "exp_gained": exp_gained,  # 本次获得的经验值
        "difficulty": exercise.difficulty,
    }
