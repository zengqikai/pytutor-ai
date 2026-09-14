"""
学习画像服务
============

管理学生学习画像的生命周期：
- 创建画像（注册时自动创建）
- 更新画像（每次学习行为后）
- 薄弱知识点检测
- 学习路径推荐
"""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import LearningEvent, StudentProfile, StudentWeakness
from app.observability.logger import get_logger

logger = get_logger(__name__)

# 知识点依赖关系（前置知识 → 后续知识）
CONCEPT_PREREQUISITES = {
    "variables": [],
    "data_types": ["variables"],
    "string": ["data_types"],
    "list": ["data_types"],
    "dict": ["data_types"],
    "tuple": ["list"],
    "set": ["list"],
    "for_loop": ["list", "string"],
    "while_loop": ["for_loop"],
    "if_statement": ["data_types"],
    "function": ["for_loop", "if_statement"],
    "class": ["function"],
    "exception": ["if_statement", "function"],
    "file_io": ["function", "string"],
    "list_comprehension": ["for_loop", "list"],
}

# 推荐学习路径（按顺序）
LEARNING_PATH = [
    "variables", "data_types", "string", "list", "tuple",
    "if_statement", "for_loop", "while_loop", "dict", "set",
    "function", "exception", "list_comprehension", "file_io", "class",
]


async def get_or_create_profile(db: AsyncSession, user_id: str) -> StudentProfile:
    """获取或创建学习画像。"""
    result = await db.execute(
        select(StudentProfile).where(StudentProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        profile = StudentProfile(user_id=user_id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        logger.info("profile_created", user_id=user_id)

    return profile


async def record_event(
    db: AsyncSession,
    user_id: str,
    event_type: str,
    concept: str | None = None,
    detail: dict | None = None,
):
    """记录学习事件并更新画像。"""
    # 保存事件
    event = LearningEvent(
        user_id=user_id,
        event_type=event_type,
        concept=concept,
        detail_json=json.dumps(detail, ensure_ascii=False) if detail else None,
    )
    db.add(event)

    # 更新画像统计
    profile = await get_or_create_profile(db, user_id)
    if event_type == "exercise_passed":
        profile.total_exercises_completed += 1
        profile.total_exercises_passed += 1
    elif event_type == "exercise_failed":
        profile.total_exercises_completed += 1
    elif event_type == "code_submitted":
        profile.total_code_submissions += 1
    elif "hint" in event_type:
        profile.total_hints_used += 1

    # ---- C 方向 Task 4: Hint Dependency 自动量化 ----
    # 纯计数器运算（零 LLM 调用），始终执行，无需 Feature Flag
    if "hint" in event_type:
        from app.services.profile_decay_service import update_hint_dependency
        try:
            await update_hint_dependency(db, user_id, profile)
        except Exception:
            pass  # 不影响主流程

    await db.commit()


async def update_weakness(
    db: AsyncSession,
    user_id: str,
    concept: str,
    error_type: str | None = None,
    is_success: bool = False,
):
    """
    更新薄弱知识点。

    规则：
    - 失败 → fail_count += 1, severity = min(5, fail_count)
    - 连续 3 次失败 → 标记为薄弱点
    - 成功 → 重置 fail_count, 标记 resolved
    """
    result = await db.execute(
        select(StudentWeakness)
        .where(
            StudentWeakness.user_id == user_id,
            StudentWeakness.concept == concept,
            StudentWeakness.is_resolved == False,
        )
    )
    weakness = result.scalar_one_or_none()

    if is_success:
        if weakness:
            weakness.is_resolved = True
            logger.info("weakness_resolved", user_id=user_id, concept=concept)
    else:
        if weakness:
            weakness.fail_count += 1
            weakness.last_error_type = error_type
            # 严重度 = 连续失败次数，4+ 次封顶
            # 1→Lv1, 2→Lv2, 3→Lv3, 4→Lv4, 5+→Lv5
            weakness.severity = min(5, weakness.fail_count)
        else:
            weakness = StudentWeakness(
                user_id=user_id,
                concept=concept,
                fail_count=1,
                severity=1,
                last_error_type=error_type,
            )
            db.add(weakness)
        logger.info("weakness_updated", user_id=user_id, concept=concept, fail_count=weakness.fail_count)

    await db.commit()


async def get_weaknesses(db: AsyncSession, user_id: str) -> list[dict]:
    """获取当前未解决的薄弱知识点。"""
    from app.core.config import settings

    result = await db.execute(
        select(StudentWeakness)
        .where(
            StudentWeakness.user_id == user_id,
            StudentWeakness.is_resolved == False,
        )
        .order_by(StudentWeakness.severity.desc())
    )
    weaknesses = result.scalars().all()

    weak_list = [
        {
            "concept": w.concept,
            "fail_count": w.fail_count,
            "severity": w.severity,
            "last_error": w.last_error_type,
            "created_at": w.created_at.isoformat(),
        }
        for w in weaknesses
    ]

    # ---- C 方向 Task 3: 时间衰减 ----
    if settings.ENABLE_TIME_DECAY and weak_list:
        from app.services.profile_decay_service import decay_all_weaknesses, TRANSITION_MATRIX_CACHE
        weak_list = decay_all_weaknesses(weak_list)
        logger.info("weaknesses_decayed",
                    user_id=user_id,
                    count=len(weak_list),
                    top_before=weak_list[0].get("severity_raw"),
                    top_after=weak_list[0].get("severity_decayed"))

    return weak_list


async def get_recommendation(db: AsyncSession, user_id: str) -> dict:
    """
    推荐下一步学习内容。

    推荐逻辑：
    1. 如果有薄弱点 → 推荐最严重的一个（需要复习）
    2. 如果无薄弱点 → 推荐学习路径上的下一个知识点
    3. 优先推荐有前置知识已完成的
    """
    from app.core.config import settings

    profile = await get_or_create_profile(db, user_id)

    # 解析已掌握的知识点
    mastery = {}
    if profile.concept_mastery_json:
        try:
            mastery = json.loads(profile.concept_mastery_json)
        except json.JSONDecodeError:
            pass

    # 先检查薄弱点
    weaknesses = await get_weaknesses(db, user_id)
    if weaknesses:
        weakest = weaknesses[0]

        # ---- C 方向 Task 3: 转移矩阵增强推荐 ----
        extra_info = ""
        decay_info = ""
        risk_warning = ""

        if settings.ENABLE_TIME_DECAY:
            # 使用衰减后严重度
            decayed = weakest.get("severity_decayed", weakest["severity"])
            if decayed < 1.0 and decayed < weakest.get("severity_raw", 1):
                days = weakest.get("days_since", 0)
                decay_info = f"（{days:.0f}天前，严重度已自然衰减至 {decayed:.1f}）"

            # 转移矩阵：预测风险概念
            from app.services.profile_decay_service import TRANSITION_MATRIX_CACHE
            weak_concepts = [w["concept"] for w in weaknesses[:3]]
            tm = TRANSITION_MATRIX_CACHE.get()
            if tm is not None:
                risks = tm.predict_weakness_risk(weak_concepts)
                if risks:
                    risk_concepts = ", ".join(
                        f"{r['concept']}({r['risk_score']:.0%})" for r in risks[:2]
                    )
                    risk_warning = f" 同时注意：{risk_concepts} 也有变弱风险。"

            # 使用衰减后严重度判断是否需要复习
            if decayed < 1.5:  # 衰减到很低 → 可能已经会了
                logger.info("recommendation_decay_skip",
                            user_id=user_id, concept=weakest["concept"],
                            decayed=decayed)
                # 不推荐复习，走正常学习路径
                weaknesses = []

        if weaknesses:
            severity_val = weakest.get("severity_decayed", weakest["severity"])
            reason = (
                f"你在 '{weakest['concept']}' 上失败了 {weakest['fail_count']} 次，"
                f"建议重点复习。{decay_info}{risk_warning}"
            )
            result = {
                "action": "review",
                "concept": weakest["concept"],
                "reason": reason.strip(),
                "severity": round(float(severity_val), 1),
            }

            # ---- C 方向 Task 5: Content-Based 练习推荐 ----
            if settings.ENABLE_CONTENT_RECOMMEND:
                try:
                    exercises = await get_content_recommendations(db, user_id, top_k=5)
                    if exercises:
                        result["recommended_exercises"] = exercises
                        result["reason"] += (
                            f" 为你推荐了 {len(exercises)} 道相关练习题。"
                        )
                        logger.info("content_recommend_added",
                                    user_id=user_id, count=len(exercises),
                                    top_score=exercises[0]["score"])
                except Exception:
                    pass  # 推荐失败不影响主推荐

            return result

    # 推荐下一个知识点
    for concept in LEARNING_PATH:
        if concept not in mastery or mastery[concept] < 0.6:
            prerequisites = CONCEPT_PREREQUISITES.get(concept, [])
            prereqs_met = all(
                p in mastery and mastery[p] >= 0.5 for p in prerequisites
            )
            if prereqs_met:
                return {
                    "action": "learn",
                    "concept": concept,
                    "reason": f"你已经准备好学习 '{concept}'！",
                }

    # 所有基础知识点已完成 → 推荐进阶
    return {
        "action": "advance",
        "concept": "project",
        "reason": "基础扎实！可以尝试综合项目练习。",
    }


# =============================================================================
# Content-Based 练习推荐 (C 方向 Task 5)
# =============================================================================

# 知识点描述 (TF-IDF 词汇)
CONCEPT_KEYWORDS: dict[str, list[str]] = {
    "variables": ["变量", "赋值", "名字", "值", "类型", "整数", "字符串"],
    "data_types": ["类型", "int", "str", "float", "bool", "转换", "type"],
    "string": ["字符串", "拼接", "切片", "format", "f-string", "len", "upper", "lower"],
    "list": ["列表", "append", "索引", "切片", "遍历", "sort", "pop", "元素"],
    "dict": ["字典", "键", "值", "key", "value", "items", "get", "遍历"],
    "tuple": ["元组", "不可变", "打包", "解包", "逗号"],
    "set": ["集合", "去重", "交集", "并集", "差集", "add", "remove"],
    "for_loop": ["for", "循环", "range", "遍历", "迭代", "break", "continue"],
    "while_loop": ["while", "条件", "无限", "计数器", "循环", "break"],
    "if_statement": ["if", "elif", "else", "条件", "判断", "比较", "布尔"],
    "function": ["函数", "def", "return", "参数", "调用", "作用域", "lambda"],
    "class": ["类", "对象", "class", "self", "__init__", "方法", "属性", "继承"],
    "exception": ["异常", "try", "except", "错误", "raise", "finally", "捕获"],
    "file_io": ["文件", "open", "read", "write", "with", "路径", "关闭"],
    "list_comprehension": ["列表推导", "生成器", "推导式", "for in if", "简洁"],
}


def compute_concept_similarity(concept_a: str, concept_b: str) -> float:
    """
    基于关键词 Jaccard 相似度计算两个概念的关联度。

    用于推荐系统：匹配学生弱项与练习知识点。

    无需外部 Embedding API，纯本地计算。
    """
    kw_a = set(CONCEPT_KEYWORDS.get(concept_a, [concept_a]))
    kw_b = set(CONCEPT_KEYWORDS.get(concept_b, [concept_b]))

    if not kw_a or not kw_b:
        return 0.0

    intersection = kw_a & kw_b
    union = kw_a | kw_b

    if not union:
        return 0.0

    return round(len(intersection) / len(union), 3)


async def get_content_recommendations(
    db: AsyncSession,
    user_id: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Content-Based 练习推荐。

    算法:
    1. 获取学生弱项概念列表
    2. 对数据库中所有可用练习，计算概念相似度加权分
    3. 返回 top-k

    参数:
        db: 数据库会话
        user_id: 用户 ID
        top_k: 推荐数量

    返回:
        [{"exercise_id": str, "title": str, "score": float, "reason": str}, ...]
    """
    from sqlalchemy import select as sa_select
    from app.models.exercise import Exercise

    # 获取弱项
    weaknesses = await get_weaknesses(db, user_id)
    weak_concepts = [w["concept"] for w in weaknesses[:5]]  # top 5 弱项

    if not weak_concepts:
        return []

    # 获取所有可用练习
    result = await db.execute(
        sa_select(Exercise).where(Exercise.is_published == True).limit(100)
    )
    exercises = result.scalars().all()

    if not exercises:
        return []

    # 打分：对每道题，计算与弱项概念的最大相似度 × (1 - 0.1 × difficulty_diff)
    # difficulty_diff = |练习难度 - 学生等级对应难度|
    profile = await get_or_create_profile(db, user_id)
    student_level = profile.level  # 1-10
    # 映射学生等级到练习难度 (1-5)
    appropriate_difficulty = max(1, min(5, (student_level + 1) // 2))

    scored = []
    for ex in exercises:
        # 解析练习的 concepts（逗号分隔字符串）
        ex_concepts = [c.strip() for c in (ex.concepts or "python_basics").split(",") if c.strip()]

        # 最佳匹配：弱项概念与练习概念的最大 Jaccard 相似度
        best_sim = 0.0
        for wc in weak_concepts:
            for ec in ex_concepts:
                sim = compute_concept_similarity(wc, ec)
                if sim > best_sim:
                    best_sim = sim

        # 难度惩罚: 难度差距越大，分数越低
        diff_penalty = 1.0 - 0.1 * abs(ex.difficulty - appropriate_difficulty)
        diff_penalty = max(0.5, diff_penalty)  # 最低 50% 的权重

        final_score = best_sim * diff_penalty

        if final_score > 0.05:  # 最低相似度阈值
            scored.append({
                "exercise_id": ex.id,
                "title": ex.title,
                "difficulty": ex.difficulty,
                "concepts": ex.concepts,
                "score": round(final_score, 3),
                "reason": f"与你的弱项 '{weak_concepts[0]}' 相关 (相似度 {best_sim:.0%})",
            })

    # 按分数降序排列
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


async def get_profile_summary(db: AsyncSession, user_id: str) -> dict:
    """获取画像摘要，供前端 Dashboard 展示。"""
    profile = await get_or_create_profile(db, user_id)
    weaknesses = await get_weaknesses(db, user_id)
    recommendation = await get_recommendation(db, user_id)

    # 计算练习通过率 + 经验值
    total = profile.total_exercises_completed
    passed = profile.total_exercises_passed
    pass_rate = round(passed / total * 100, 1) if total > 0 else 0
    import json
    mastery = {}
    if profile.concept_mastery_json:
        try: mastery = json.loads(profile.concept_mastery_json)
        except: pass
    total_exp = mastery.get("_total_exp", 0)
    next_level_exp = (profile.level) * 300
    onboarding_done = mastery.get("_onboarding") is not None

    # 2.0 字段
    weak_topics = []
    recent_mc = []
    completed = []
    if profile.weak_topics:
        try: weak_topics = json.loads(profile.weak_topics)
        except: pass
    if profile.recent_misconceptions:
        try: recent_mc = json.loads(profile.recent_misconceptions)
        except: pass
    if profile.completed_lessons:
        try: completed = json.loads(profile.completed_lessons)
        except: pass

    return {
        "level": profile.level,
        "total_exp": total_exp,
        "next_level_exp": next_level_exp,
        "onboarding_done": onboarding_done,
        "stats": {
            "exercises_completed": total,
            "exercises_passed": passed,
            "pass_rate": pass_rate,
            "code_submissions": profile.total_code_submissions,
            "hints_used": profile.total_hints_used,
            "chat_messages": profile.total_chat_messages,
        },
        "weaknesses": weaknesses,
        "weak_topics": weak_topics,
        "recent_misconceptions": recent_mc,
        "hint_dependency": profile.hint_dependency or "low",
        "completed_lessons": completed,
        "recommendation": recommendation,
    }
