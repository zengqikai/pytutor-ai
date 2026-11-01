"""
误区诊断服务
============

规则匹配 + LLM 辅助分类双通道诊断 Python 初学者常见误区。

3.0 新增：AST 代码结构分析通道（Feature Flag: ENABLE_AST_DIAGNOSIS）

流程：
1. 规则匹配：正则扫描代码和错误信息，匹配 8 类已知误区
2. [3.0] AST 结构分析：当 ENABLE_AST_DIAGNOSIS=true 时优先
3. LLM 辅助：规则/AST 不确定时调用 LLM 分类
4. 返回结构化诊断结果（向后兼容）
"""

import json
import re
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.misconception import Misconception, MisconceptionEvent
from app.observability.logger import get_logger

logger = get_logger(__name__)

# 加载误区定义
_misconceptions_cache: Optional[list[dict]] = None


def _load_misconceptions() -> list[dict]:
    global _misconceptions_cache
    if _misconceptions_cache is None:
        path = Path(__file__).resolve().parent.parent / "data" / "misconceptions.json"
        with open(path, encoding="utf-8") as f:
            _misconceptions_cache = json.load(f)
    return _misconceptions_cache


def _rule_match(code: str, stderr: str, mc: dict) -> bool:
    """对单个误区执行规则匹配。"""
    patterns = mc.get("typical_patterns", [])
    text = code + "\n" + (stderr or "")
    for pattern in patterns:
        try:
            if re.search(pattern, text, re.MULTILINE | re.DOTALL):
                return True
        except re.error:
            continue
    return False


async def diagnose(
    db: AsyncSession,
    code: str,
    stderr: str = "",
    exercise_context: Optional[str] = None,
) -> dict:
    """
    诊断学生代码中的 Python 误区。

    3.0 增强：当 ENABLE_AST_DIAGNOSIS=true 时，优先使用 AST 结构分析；
    AST 无命中或解析失败时 fallback 到规则匹配 + LLM。

    参数:
        db: 数据库会话
        code: 学生代码
        stderr: 运行错误信息
        exercise_context: 题目要求（可选）

    返回:
        {
            "has_misconception": bool,
            "misconception_id": str | None,
            "misconception_name": str | None,
            "confidence": float,
            "evidence": str,
            "related_concepts": list[str],
            # 3.0 新增（向后兼容）
            "diagnosis_method": "ast" | "regex" | "llm" | "none",
            "ast_features": dict | None,
        }
    """
    # ---- 3.0: Feature Flag 分支 ----
    if settings.ENABLE_AST_DIAGNOSIS:
        return await _ast_diagnose(db, code, stderr, exercise_context)

    # ---- 旧逻辑：纯正则 + LLM（原封不动） ----
    misconceptions = _load_misconceptions()
    matches = []

    # 步骤 1：规则匹配
    for mc in misconceptions:
        if _rule_match(code, stderr, mc):
            matches.append({
                "misconception_id": mc["code"],
                "misconception_name": mc["name"],
                "confidence": 0.85,
                "evidence": f"代码匹配误区模式: {mc['name']}",
                "related_concepts": (mc.get("related_concepts") or "").split(","),
            })

    if matches:
        best = max(matches, key=lambda m: m["confidence"])
        logger.info("misconception_diagnosed", method="rule", code=best["misconception_id"],
                     confidence=best["confidence"])
        return {
            "has_misconception": True,
            "diagnosis_method": "regex",
            "ast_features": None,
            **best,
        }

    # 步骤 2：LLM 辅助分类
    if code.strip() and stderr and len(code.split("\n")) <= 30:
        try:
            llm_result = await _llm_classify(code, stderr)
            if llm_result and llm_result.get("misconception_id") != "none":
                logger.info("misconception_diagnosed", method="llm",
                             code=llm_result.get("misconception_id"))
                return {
                    "has_misconception": True,
                    "misconception_id": llm_result.get("misconception_id"),
                    "misconception_name": llm_result.get("misconception_name", ""),
                    "confidence": llm_result.get("confidence", 0.5),
                    "evidence": llm_result.get("evidence", "LLM 辅助分类"),
                    "related_concepts": llm_result.get("related_concepts", []),
                    "diagnosis_method": "llm",
                    "ast_features": None,
                }
        except Exception as e:
            logger.warning("llm_misconception_failed", error=str(e)[:200])

    return {
        "has_misconception": False,
        "misconception_id": None,
        "misconception_name": None,
        "confidence": 0,
        "evidence": "",
        "related_concepts": [],
        "diagnosis_method": "none",
        "ast_features": None,
    }


async def _ast_diagnose(
    db: AsyncSession,
    code: str,
    stderr: str = "",
    exercise_context: Optional[str] = None,
) -> dict:
    """
    3.0 AST 结构分析诊断通道。

    优先级：
    1. AST 解析 → 结构分析 (M3/M4/M6/M8) + 信号评分 (M5/M7)
    2. AST 失败 → M1/M2 检测 + 正则 fallback
    3. AST 无命中 → LLM 辅助分类
    """
    from app.analysis.ast_analyzer import analyze_misconceptions

    student_question = exercise_context or ""

    # ---- Step 1: AST 分析 ----
    try:
        ast_findings = analyze_misconceptions(code, stderr, student_question)
    except Exception as e:
        logger.warning("ast_analysis_exception", error=str(e)[:200])
        ast_findings = []

    if ast_findings:
        # SRS 3.2 接线：排序沿用 visitor 的规则先验（各规则特异性排序，
        # 评测行为不变），但对外报告的 confidence 换成证据折算值——
        # 硬编码常数只用于排序，不再冒充置信度（问题清单 A3 的闭环）。
        from app.analysis.confidence import from_visitor_finding

        for f in ast_findings:
            try:
                cr = from_visitor_finding(f, stderr=stderr)
                f["confidence"] = cr.confidence
                f["confidence_terms"] = cr.terms
            except Exception as e:  # 折算失败保留原值，不阻断诊断
                logger.warning("confidence_engine_failed", error=str(e)[:200])

        best = ast_findings[0]
        logger.info(
            "misconception_diagnosed",
            method="ast",
            code=best.get("misconception_id"),
            confidence=best.get("confidence"),
            ast_finding_count=len(ast_findings),
        )
        return {
            "has_misconception": True,
            "misconception_id": best.get("misconception_id"),
            "misconception_name": best.get("misconception_name"),
            "confidence": best.get("confidence", 0),
            "evidence": best.get("evidence", ""),
            "related_concepts": best.get("related_concepts", []),
            "diagnosis_method": best.get("diagnosis_method", "ast"),
            "ast_features": best.get("ast_features"),
            "confidence_terms": best.get("confidence_terms"),
            # 多误区共存信息不再在服务边界丢弃（root_cause 层的数据来源）
            "all_findings": [
                {k: f.get(k) for k in (
                    "misconception_id", "misconception_name",
                    "confidence", "evidence", "ast_features",
                )}
                for f in ast_findings
            ],
        }

    # ---- Step 2: AST 无命中 → fallback 到 LLM ----
    if code.strip() and stderr and len(code.split("\n")) <= 30:
        try:
            llm_result = await _llm_classify(code, stderr)
            if llm_result and llm_result.get("misconception_id") != "none":
                logger.info("misconception_diagnosed", method="llm_fallback",
                             code=llm_result.get("misconception_id"))
                return {
                    "has_misconception": True,
                    "misconception_id": llm_result.get("misconception_id"),
                    "misconception_name": llm_result.get("misconception_name", ""),
                    "confidence": llm_result.get("confidence", 0.5),
                    "evidence": llm_result.get("evidence", "LLM 辅助分类（AST 无命中后 fallback）"),
                    "related_concepts": llm_result.get("related_concepts", []),
                    "diagnosis_method": "llm",
                    "ast_features": None,
                }
        except Exception as e:
            logger.warning("llm_misconception_failed", error=str(e)[:200])

    # ---- Step 3: 完全无命中 ----
    return {
        "has_misconception": False,
        "misconception_id": None,
        "misconception_name": None,
        "confidence": 0,
        "evidence": "",
        "related_concepts": [],
        "diagnosis_method": "ast",
        "ast_features": None,
    }


async def _llm_classify(code: str, stderr: str) -> Optional[dict]:
    """LLM 辅助误区分类。"""
    from app.services.llm_service import chat_completion
    from app.schemas.ai import ChatMessage

    misconceptions = _load_misconceptions()
    mc_desc = "\n".join([
        f"- {m['code']}: {m['name']} — {m['description']}"
        for m in misconceptions
    ])

    prompt = f"""你是 Python 教学专家。请判断以下学生代码是否存在以下常见误区之一。

常见误区：
{mc_desc}

学生代码：
```python
{code[:500]}
```

错误信息：
{stderr[:300]}

请以 JSON 格式回复（不要其他文字）：
{{"misconception_id": "M1-M8 或 none", "misconception_name": "误区名", "confidence": 0.0-1.0, "evidence": "简短依据", "related_concepts": ["concept1"]}}"""

    response = await chat_completion(
        messages=[ChatMessage(role="user", content=prompt)],
        temperature=0.1,
        max_tokens=200,
    )

    # 尝试解析 JSON
    content = response.content.strip()
    import re as _re
    json_match = _re.search(r'\{.*\}', content, _re.DOTALL)
    if json_match:
        return json.loads(json_match.group())
    return None


async def seed_misconceptions(db: AsyncSession) -> int:
    """将误区种子数据写入数据库（幂等）。"""
    existing = (await db.execute(select(Misconception))).scalars().all()
    if existing:
        return len(existing)

    misconceptions = _load_misconceptions()
    count = 0
    for mc in misconceptions:
        m = Misconception(
            code=mc["code"],
            name=mc["name"],
            description=mc["description"],
            typical_patterns=json.dumps(mc.get("typical_patterns", [])),
            related_concepts=mc.get("related_concepts", ""),
            recommended_strategy=mc.get("recommended_strategy", "progressive_hint"),
        )
        db.add(m)
        count += 1

    await db.commit()
    logger.info("misconceptions_seeded", count=count)
    return count


async def resolve_misconception_pk(db: AsyncSession, misconception_ref: str) -> str | None:
    """把业务编号（M1–M8）解析为 misconceptions.id 主键；已是主键则原样返回。

    诊断链路产出的是 `M7` 这类业务编号，而 misconception_events.misconception_id
    是指向 misconceptions.id 的外键。两者混用会写入孤儿记录（SQLite 不报错，
    PostgreSQL 会直接失败），因此所有写入前都必须经过本函数。
    """
    if not misconception_ref:
        return None

    result = await db.execute(select(Misconception.id).where(Misconception.id == misconception_ref))
    if result.scalar_one_or_none():
        return misconception_ref

    result = await db.execute(select(Misconception.id).where(Misconception.code == misconception_ref))
    return result.scalar_one_or_none()


async def record_misconception_event(
    db: AsyncSession,
    user_id: str,
    misconception_id: str,
    confidence: float,
    evidence: str,
    code_snippet: str = "",
    submission_id: str = "",
    exercise_id: str = "",
) -> MisconceptionEvent:
    """记录一次误区诊断事件。

    `misconception_id` 可以是主键或业务编号，内部统一解析为主键。
    无法解析时抛 ValueError，避免静默写入脏数据。
    """
    pk = await resolve_misconception_pk(db, misconception_id)
    if pk is None:
        raise ValueError(
            f"未知误区标识 {misconception_id!r}：既不是 misconceptions.id 主键，"
            f"也不是已注册的 code"
        )

    event = MisconceptionEvent(
        user_id=user_id,
        misconception_id=pk,
        submission_id=submission_id or None,
        exercise_id=exercise_id or None,
        confidence=confidence,
        evidence=evidence,
        code_snippet=code_snippet[:500] if code_snippet else None,
    )
    db.add(event)

    # 同步画像的"最近误区"字段：聊天和教师看板都直接读这个字段，
    # 不维护它就会出现"误区事件有记录、画像永远是空"的分裂。
    try:
        import json as _json
        from app.services.profile_service import get_or_create_profile
        mc = await db.get(Misconception, pk)
        code = mc.code if mc else misconception_id
        profile = await get_or_create_profile(db, user_id)
        recent: list[str] = []
        if profile.recent_misconceptions:
            try:
                parsed = _json.loads(profile.recent_misconceptions)
                if isinstance(parsed, list):
                    recent = [str(x) for x in parsed]
            except (ValueError, TypeError):
                recent = []
        recent.append(code)
        # 去重保留最近出现的顺序，最多 10 条
        deduped: list[str] = []
        for c in reversed(recent):
            if c not in deduped:
                deduped.append(c)
        profile.recent_misconceptions = _json.dumps(
            list(reversed(deduped))[:10], ensure_ascii=False
        )
    except Exception as exc:
        logger.warning("profile_misconception_update_failed",
                       user_id=user_id, error=str(exc)[:200])

    # 只 flush 不 commit：这里在请求中途，commit 会把调用方尚未写完的其它
    # 改动（消息、画像、经验值）一起提前提交，失败时也无法整体回滚。
    # 统一交给调用方或 get_db 的收尾 commit。
    await db.flush()
    return event


async def get_user_misconceptions(db: AsyncSession, user_id: str, limit: int = 20):
    """获取用户最近的误区记录。"""
    result = await db.execute(
        select(MisconceptionEvent, Misconception)
        .join(Misconception, MisconceptionEvent.misconception_id == Misconception.id, isouter=True)
        .where(MisconceptionEvent.user_id == user_id)
        .order_by(MisconceptionEvent.created_at.desc())
        .limit(limit)
    )
    rows = result.all()
    return [
        {
            "id": event.id,
            "misconception_code": mc.code if mc else None,
            "misconception_name": mc.name if mc else None,
            "confidence": event.confidence,
            "evidence": event.evidence,
            "code_snippet": event.code_snippet,
            "time": event.created_at.isoformat(),
        }
        for event, mc in rows
    ]


async def get_misconception_history_count(
    db: AsyncSession,
    user_id: str,
    misconception_code: str,
) -> int:
    """返回该学生该误区的历史命中次数（不含本次调用后的记录）。

    用于 select_strategy() 计算真实的 attempt_count 和 has_history。
    """
    from sqlalchemy import func as sa_func
    result = await db.execute(
        select(sa_func.count())
        .select_from(MisconceptionEvent)
        .join(Misconception, MisconceptionEvent.misconception_id == Misconception.id)
        .where(
            MisconceptionEvent.user_id == user_id,
            Misconception.code == misconception_code,
        )
    )
    return result.scalar() or 0
