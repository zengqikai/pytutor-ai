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

    # 2.0: 误区诊断 + 教学策略 → 渐进式提示
    misconception = None
    try:
        from app.services.misconception_service import diagnose as mc_diagnose
        stderr_info = failed_info if failed_info else ""
        mc_result = await mc_diagnose(db, code=user_code, stderr=stderr_info)
        if mc_result.get("has_misconception"):
            misconception = mc_result
    except Exception:
        pass

    # 根据误区和尝试次数确定提示等级
    effective_level = level
    strategy_name = "progressive_hint"
    mc_name = misconception["misconception_name"] if misconception else None

    if misconception and level <= 2:
        # 首次误区 → 概念提示 + 反例
        strategy_name = "counterexample" if level == 1 else "concept_explanation"
        effective_level = 1 if level == 1 else 2
    elif level >= 5:
        effective_level = 5
        strategy_name = "summary_reflection"

    hint_prompts = {
        1: f"学生正在做：{exercise.title}。诊断出误区：{mc_name or '未知'}。请给 Level 1 概念提示——只解释相关概念，不涉及代码位置，不直接给答案。2-3 句中文。",
        2: f"学生正在做：{exercise.title}。误区：{mc_name or '未知'}。请给 Level 2 方向提示——给出解决方向，用问题引导学生思考，不指出具体行。2-3 句中文。",
        3: f"学生正在做：{exercise.title}。误区：{mc_name or '未知'}。学生代码：\n```python\n{user_code[:300]}\n```\n请给 Level 3 位置提示——指出可疑代码区域，但不给正确代码。2-3 句中文。",
        4: f"学生正在做：{exercise.title}。误区：{mc_name or '未知'}。学生代码：\n```python\n{user_code[:400]}\n```\n请给 Level 4 部分代码——给出关键片段，但保留部分让学生完成。",
        5: f"学生正在做：{exercise.title}。完整题目：{exercise.description[:400]}\n请给 Level 5 完整参考答案，附带逐行解释。",
    }

    prompt = hint_prompts.get(min(effective_level, 5), hint_prompts[2])
    max_tokens = 200 if effective_level <= 2 else 400

    try:
        llm_resp = await chat_completion(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.5, max_tokens=max_tokens,
        )
        return {
            "hint": llm_resp.content.strip(),
            "hint_level": effective_level,
            "misconception_id": misconception["misconception_id"] if misconception else None,
            "misconception_name": mc_name,
            "strategy": strategy_name,
        }
    except Exception as e:
        from app.observability.logger import get_logger
        get_logger(__name__).warning("hint_generation_failed", error=str(e)[:200])
        return {"hint": "提示生成暂时失败，请稍后重试", "hint_level": effective_level}


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

    # 2.0: 误区诊断（未全部通过时触发）
    misconception_diagnosis = None
    if not (passed == total and total > 0):
        try:
            from app.services.misconception_service import diagnose as mc_diagnose
            stderr_summary = "; ".join([
                t.get("error", "") for t in test_results if not t.get("passed")
            ])[:500]
            mc_result = await mc_diagnose(
                db, code=user_code, stderr=stderr_summary,
                exercise_context=exercise.description or ""
            )
            if mc_result.get("has_misconception"):
                misconception_diagnosis = mc_result
        except Exception:
            pass

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

    # 去重检查：按题目 ID 判断是否首次通过（而非按概念标签）
    from app.models.profile import LearningEvent
    from sqlalchemy import select, func as _sa_func
    already_passed = (await db.execute(
        select(_sa_func.count()).select_from(LearningEvent)
        .where(LearningEvent.user_id == current_user.id, LearningEvent.event_type == "exercise_passed",
               LearningEvent.detail_json.like(f'%"{exercise.id}"%'))
    )).scalar() or 0

    # 首次通过该题目才创建 exercise_passed 事件
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

    # record_event() 已经更新了 total_exercises_completed/passed/hints_used
    # 这里只更新 experience 和 concept_mastery，避免双重计数
    if all_passed and score_pct > 0 and already_passed == 0 and used_hints > 0:
        profile.total_hints_used += used_hints

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
        "exp_gained": exp_gained,
        "difficulty": exercise.difficulty,
        # 2.0: 误区诊断结果
        "misconception": misconception_diagnosis,
    }
