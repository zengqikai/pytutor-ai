"""
画像时间衰减 + 知识转移矩阵服务 (C 方向 Task 3)
================================================

解决两个问题：
1. **时间衰减**：弱项 severity 随时间自然衰减，防止"3 周前犯过错"永久标记为弱项
2. **知识转移矩阵**：追踪知识点间掌握概率转移，预测"学好 A 后 B 是否也会提高"

核心设计决策：
1. **指数衰减**：severity_t = severity_0 × e^(-λ × days_since)
   - 半衰期默认 7 天 (DAYS_HALF_LIFE=7)
   - λ = ln(2) / HALF_LIFE
2. **马尔可夫转移矩阵**：基于 LearningEvent 历史计算
   - 状态定义: weak(0-0.3) / developing(0.3-0.6) / proficient(0.6-1.0)
   - 转移概率: P(concept_B→state_X | concept_A→state_Y) 用贝叶斯平滑估计
3. **弱项预测准确率**：测"推荐复习后学生续错的概率"作为核心指标

文献依据：
- TRAVER (ACL 2025 Findings): 知识追踪中时间衰减 + 转移关系优于静态模型
- Code-DKT: 专用知识追踪小模型在成本/延迟/准确率上优于 LLM
- Ebbinghaus 遗忘曲线: 指数衰减模型在认知技能学习中仍是最佳简单拟合

作者: clt (C 方向)
日期: 2026-07-27
"""

import json
import math
import time
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.profile import LearningEvent, StudentProfile, StudentWeakness
from app.observability.logger import get_logger

logger = get_logger(__name__)

# =============================================================================
# 配置常量
# =============================================================================

# 半衰期：7 天后 severity 降低一半
DAYS_HALF_LIFE = 7.0
DECAY_LAMBDA = math.log(2) / DAYS_HALF_LIFE  # ≈ 0.099

# 掌握度阈值
MASTERY_THRESHOLDS = {
    "weak": (0.0, 0.3),       # 薄弱
    "developing": (0.3, 0.6),  # 发展中
    "proficient": (0.6, 1.0),  # 熟练
}

# 知识点列表（对齐 profile_service.py 中的 LEARNING_PATH）
ALL_CONCEPTS = [
    "variables", "data_types", "string", "list", "tuple",
    "if_statement", "for_loop", "while_loop", "dict", "set",
    "function", "exception", "list_comprehension", "file_io", "class",
]


# =============================================================================
# 状态判定工具
# =============================================================================

def mastery_to_state(mastery: float) -> str:
    """将掌握度 (0.0-1.0) 映射为离散状态。"""
    if mastery < 0.3:
        return "weak"
    elif mastery < 0.6:
        return "developing"
    else:
        return "proficient"


def state_to_center(state: str) -> float:
    """状态对应的中心值（用于数值计算）。"""
    return {"weak": 0.15, "developing": 0.45, "proficient": 0.80}[state]


# =============================================================================
# 1. 时间衰减 (Time Decay)
# =============================================================================

def compute_decayed_severity(
    severity: int,
    last_updated_at: datetime,
    reference_time: datetime | None = None,
) -> dict:
    """
    对弱项严重度应用指数时间衰减。

    公式: severity_t = severity_0 × e^(-λ × t)
    其中 λ = ln(2) / HALF_LIFE_DAYS

    参数:
        severity: 原始严重度 (1-5)
        last_updated_at: 最后一次更新的时间
        reference_time: 参考时间 (None = 当前 UTC)

    返回:
        {"raw": int, "decayed": float, "days_since": float, "half_lives": float}
    """
    ref = reference_time or datetime.now(timezone.utc)
    # 处理 naive datetime → 假设 UTC
    if last_updated_at.tzinfo is None:
        last_updated_at = last_updated_at.replace(tzinfo=timezone.utc)

    delta = ref - last_updated_at
    days_since = delta.total_seconds() / 86400.0

    # 未来时间（不应出现，但防护）
    if days_since < 0:
        days_since = 0.0

    # 指数衰减
    decay_factor = math.exp(-DECAY_LAMBDA * days_since)
    decayed = severity * decay_factor

    # 保留最小 0.1（彻底遗忘 ≠ 从未犯错）
    decayed = max(0.1, decayed)

    return {
        "raw": severity,
        "decayed": round(decayed, 2),
        "days_since": round(days_since, 1),
        "half_lives": round(days_since / DAYS_HALF_LIFE, 1),
        "decay_factor": round(decay_factor, 4),
    }


def decay_all_weaknesses(
    weaknesses: list[dict],
    reference_time: datetime | None = None,
) -> list[dict]:
    """
    对弱项列表全部应用时间衰减，并按衰减后严重度重新排序。

    参数:
        weaknesses: [{"concept": str, "severity": int, "created_at": str}, ...]
        reference_time: 参考时间

    返回:
        按 decayed_severity 降序排列的弱项列表（附加值 decay_info）
    """
    ref = reference_time or datetime.now(timezone.utc)
    decayed: list[dict] = []

    for w in weaknesses:
        created_at = w.get("created_at")
        if isinstance(created_at, str):
            # 兼容 ISO 格式字符串
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        severity = w.get("severity", 1)
        raw_severity = severity if isinstance(severity, int) else int(severity)

        info = compute_decayed_severity(raw_severity, created_at, ref)
        decayed.append({
            **w,
            "severity_raw": info["raw"],
            "severity_decayed": info["decayed"],
            "days_since": info["days_since"],
            "half_lives": info["half_lives"],
        })

    # 按衰减后严重度降序
    decayed.sort(key=lambda x: x["severity_decayed"], reverse=True)
    return decayed


# =============================================================================
# 2. 知识转移矩阵 (Knowledge Transition Matrix)
# =============================================================================

class TransitionMatrix:
    """
    知识点间掌握转移矩阵。

    基于历史 LearningEvent 构建：当学生先在一个知识点上失败、后在另一知识点上成功
    （或反之），记录一次跨知识点转移。

    矩阵结构: M[from_concept][to_concept] = {
        "total": int,           # 总转移观测次数
        "from_weak_to_strong": int,  # from 改善后 to 也改善
        "from_strong_to_weak": int,  # from 恶化后 to 也恶化
        "conditional_prob": float,   # P(to 变化 | from 变化)
    }

    贝叶斯平滑：使用 Beta(α=1, β=1) 先验 (Laplace smoothing)
        P_smoothed = (count + α) / (total + α + β)
        等价于初始假设每种转移发生和不发生的概率相等
    """

    # 贝叶斯平滑参数
    ALPHA = 1.0  # 伪计数：转移发生
    BETA = 1.0   # 伪计数：转移未发生

    def __init__(self):
        # 内部存储: {from_concept: {to_concept: {"total": int, "improved": int, "worsened": int}}}
        self._matrix: dict[str, dict[str, dict[str, int]]] = defaultdict(
            lambda: defaultdict(lambda: {"total": 0, "improved": 0, "worsened": 0})
        )

    def record_transition(
        self,
        from_concept: str,
        to_concept: str,
        from_improved: bool,  # from_concept 是否变好了
        to_improved: bool,     # to_concept 是否也变好了
    ):
        """记录一次跨知识点转移。"""
        cell = self._matrix[from_concept][to_concept]
        cell["total"] += 1
        if from_improved and to_improved:
            cell["improved"] += 1
        elif not from_improved and not to_improved:
            cell["worsened"] += 1

    def get_correlation(self, from_concept: str, to_concept: str) -> float:
        """
        获取两个知识点的转移相关性（贝叶斯平滑 Cohen-like 统计量）。

        返回 -1.0 到 1.0 之间的值:
        - > 0: 正向转移（学好 from → to 也会好）
        - < 0: 负向转移（学好 from → to 反而差，不太可能但保留可能性）
        - ≈ 0: 无显著转移关系
        """
        cell = self._matrix.get(from_concept, {}).get(to_concept)
        if cell is None or cell["total"] == 0:
            return 0.0

        total = cell["total"]
        improved = cell["improved"]
        worsened = cell["worsened"]

        # 贝叶斯平滑后的正向转移概率
        p_improved = (improved + self.ALPHA) / (total + self.ALPHA + self.BETA)
        p_worsened = (worsened + self.ALPHA) / (total + self.ALPHA + self.BETA)

        # Cohen-like 效应量: (p_improved - p_worsened) / sqrt(p_pooled × (1-p_pooled))
        p_pooled = (improved + worsened + 2 * self.ALPHA) / (total + self.ALPHA + self.BETA + self.ALPHA)
        if p_pooled <= 0 or p_pooled >= 1:
            return 0.0

        effect = (p_improved - p_worsened) / math.sqrt(p_pooled * (1 - p_pooled))
        return round(max(-1.0, min(1.0, effect)), 4)

    def get_related_concepts(
        self,
        concept: str,
        top_k: int = 3,
        min_correlation: float = 0.2,
    ) -> list[dict]:
        """
        获取与目标知识点最相关的其他知识点。

        只返回正相关（学好 concept → 这些也会好）超过阈值的。

        返回:
            [{"concept": str, "correlation": float, "observations": int}, ...]
        """
        if concept not in self._matrix:
            return []

        related = []
        for to_concept, cell in self._matrix[concept].items():
            corr = self.get_correlation(concept, to_concept)
            if corr >= min_correlation and cell["total"] >= 3:  # 最少 3 次观测
                related.append({
                    "concept": to_concept,
                    "correlation": corr,
                    "observations": cell["total"],
                })

        related.sort(key=lambda x: x["correlation"], reverse=True)
        return related[:top_k]

    def predict_weakness_risk(
        self,
        current_weaknesses: list[str],
    ) -> list[dict]:
        """
        基于当前弱项，预测哪些知识点也有高风险变弱。

        使用转移矩阵中的"恶化传播"模式：如果 A→B 的 worsened 概率高，
        且 A 当前是弱项，则 B 有较高风险。

        返回:
            [{"concept": str, "risk_score": float, "because_of": str}, ...]
        """
        risk_scores: dict[str, float] = {}
        risk_reasons: dict[str, list[str]] = defaultdict(list)

        for weak_concept in current_weaknesses:
            if weak_concept not in self._matrix:
                continue
            for to_concept, cell in self._matrix[weak_concept].items():
                if cell["total"] < 3:
                    continue
                # 恶化传播概率
                p_worsened = (cell["worsened"] + self.ALPHA) / (cell["total"] + self.ALPHA + self.BETA)
                if p_worsened > 0.4:  # 恶化概率 > 40%
                    risk_scores[to_concept] = risk_scores.get(to_concept, 0) + p_worsened
                    risk_reasons[to_concept].append(weak_concept)

        # 排除已知弱项
        for w in current_weaknesses:
            risk_scores.pop(w, None)

        # 排序输出
        result = []
        for concept, score in sorted(risk_scores.items(), key=lambda x: x[1], reverse=True):
            result.append({
                "concept": concept,
                "risk_score": round(min(score, 1.0), 3),
                "because_of": risk_reasons[concept][:3],
            })

        return result

    def to_dict(self) -> dict:
        """序列化为 JSON。"""
        result = {}
        for from_c, to_map in self._matrix.items():
            result[from_c] = {}
            for to_c, cell in to_map.items():
                result[from_c][to_c] = {
                    "total": cell["total"],
                    "improved": cell["improved"],
                    "worsened": cell["worsened"],
                    "correlation": self.get_correlation(from_c, to_c),
                }
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "TransitionMatrix":
        """从 JSON 反序列化。"""
        tm = cls()
        for from_c, to_map in data.items():
            for to_c, cell in to_map.items():
                tm._matrix[from_c][to_c] = {
                    "total": cell.get("total", 0),
                    "improved": cell.get("improved", 0),
                    "worsened": cell.get("worsened", 0),
                }
        return tm


# =============================================================================
# 转移矩阵缓存（进程内单例，必须在 TransitionMatrix 定义之后）
# =============================================================================
# 转移矩阵需要从历史数据构建，成本高。缓存每 30 分钟刷新一次。

class _TransitionMatrixCache:
    """转移矩阵的简单 TTL 缓存。"""

    def __init__(self):
        self._matrix: TransitionMatrix | None = None
        self._last_built: float = 0.0
        self._ttl_seconds: float = 1800.0  # 30 分钟

    def get(self) -> TransitionMatrix | None:
        """获取缓存（如果未过期）。"""
        if self._matrix is not None and (time.time() - self._last_built) < self._ttl_seconds:
            return self._matrix
        return None

    def set(self, matrix: TransitionMatrix):
        """更新缓存。"""
        self._matrix = matrix
        self._last_built = time.time()

    def invalidate(self):
        """手动失效。"""
        self._matrix = None
        self._last_built = 0.0


TRANSITION_MATRIX_CACHE = _TransitionMatrixCache()


# =============================================================================
# 3. 从历史数据构建转移矩阵
# =============================================================================

async def build_transition_matrix(
    db: AsyncSession,
    user_id: str | None = None,
    days_lookback: int = 90,
) -> TransitionMatrix:
    """
    从 LearningEvent 构建知识转移矩阵。

    算法：
    1. 查询指定时间窗口内的 LearningEvent (exercise_passed / exercise_failed)
    2. 将事件按时间排序，追踪每个知识点的掌握度变化
    3. 当一个概念的状态改变时，检查同时段其他概念是否也改变了（转移信号）

    参数:
        db: 数据库会话
        user_id: 限定某用户 (None = 全量)
        days_lookback: 回溯天数

    返回:
        TransitionMatrix: 含贝叶斯平滑的转移矩阵
    """
    cutoff = datetime.now(timezone.utc)
    # 简化：用当前时间减去天数
    from datetime import timedelta
    since = cutoff - timedelta(days=days_lookback)

    query = select(LearningEvent).where(
        LearningEvent.event_type.in_(["exercise_passed", "exercise_failed"]),
        LearningEvent.concept.isnot(None),
    )
    if user_id:
        query = query.where(LearningEvent.user_id == user_id)

    result = await db.execute(query)
    events = result.scalars().all()

    if len(events) < 10:
        logger.info("transition_matrix_insufficient_data",
                    event_count=len(events), user_id=user_id)
        return TransitionMatrix()

    # 按用户分组 → 按时间排序
    user_events: dict[str, list[LearningEvent]] = defaultdict(list)
    for e in events:
        user_events[e.user_id].append(e)

    tm = TransitionMatrix()

    for uid, evts in user_events.items():
        if len(evts) < 5:
            continue

        # 按时间排序
        evts.sort(key=lambda e: e.created_at)

        # 滑动窗口：检查相邻事件对中知识点的状态变化
        # 简化方案：对同一用户，如果 concept_a 从 fail→pass，同时 concept_b 也是 fail→pass
        # 则记录一次正向转移
        concept_last_state: dict[str, str] = {}  # concept → "pass" | "fail"

        for e in evts:
            concept = e.concept
            if not concept:
                continue
            current_state = "pass" if e.event_type == "exercise_passed" else "fail"

            if concept in concept_last_state:
                prev_state = concept_last_state[concept]

                # 检测该概念的状态变化
                from_improved = (prev_state == "fail" and current_state == "pass")

                # 检查同一用户其他概念的当前状态
                # 如果 concept 改善了，同时 other 当前是 pass → 正向转移
                for other_concept, other_state in concept_last_state.items():
                    if other_concept == concept:
                        continue
                    to_improved = (other_state == "pass")

                    tm.record_transition(concept, other_concept, from_improved, to_improved)

            concept_last_state[concept] = current_state

    logger.info("transition_matrix_built",
                users=len(user_events),
                events=len(events),
                entries=sum(len(to_map) for to_map in tm._matrix.values()))

    return tm


# =============================================================================
# 4. 弱项预测准确率测量
# =============================================================================

async def compute_weakness_prediction_accuracy(
    db: AsyncSession,
    user_id: str,
    days_window: int = 14,
) -> dict:
    """
    测量弱项推荐命中率。

    目标指标（MASTER-PLAN）：推荐"应复习的知识点"后，学生续错的概率 ≥ 70%
    即：推荐复习后，学生在该知识点上续错 → 说明推荐有效（确实薄弱）。

    方法：
    1. 回溯 days_window 天内的弱项推荐 (LearningEvent hint_requested / review_recommended)
    2. 查看推荐后 3 天内该知识点的后续事件
    3. 如果后续有 exercise_failed → 命中（推荐对了）
       如果后续有 exercise_passed 且无 fail → 未命中
       如果无后续事件 → 不确定（排除）

    返回:
        {"total_recommendations": int, "hits": int, "misses": int,
         "uncertain": int, "hit_rate": float}
    """
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days_window)

    # 查询时间窗口内的推荐相关事件
    result = await db.execute(
        select(LearningEvent).where(
            LearningEvent.user_id == user_id,
            LearningEvent.event_type.in_([
                "hint_requested",
            ]),
            LearningEvent.created_at >= since,
        )
    )
    events = result.scalars().all()

    if not events:
        return {"total_recommendations": 0, "hits": 0, "misses": 0,
                "uncertain": 0, "hit_rate": 0.0}

    # 每个推荐事件，查看后续 3 天内同概念的练习结果
    hits = 0
    misses = 0
    uncertain = 0

    for e in events:
        concept = e.concept
        if not concept:
            continue

        # 查找该推荐后 3 天内的后续事件
        follow_up_start = e.created_at
        follow_up_end = e.created_at + timedelta(days=3)

        followup_query = select(LearningEvent).where(
            LearningEvent.user_id == user_id,
            LearningEvent.concept == concept,
            LearningEvent.event_type.in_(["exercise_passed", "exercise_failed"]),
            LearningEvent.created_at > follow_up_start,
            LearningEvent.created_at <= follow_up_end,
        )
        followup_result = await db.execute(followup_query)
        followups = followup_result.scalars().all()

        if not followups:
            uncertain += 1
            continue

        # 如果有失败 → 命中
        has_fail = any(f.event_type == "exercise_failed" for f in followups)
        has_pass = any(f.event_type == "exercise_passed" for f in followups)

        if has_fail:
            hits += 1
        elif has_pass:
            misses += 1
        else:
            uncertain += 1

    total = hits + misses
    hit_rate = round(hits / total, 3) if total > 0 else 0.0

    return {
        "total_recommendations": len(events),
        "hits": hits,
        "misses": misses,
        "uncertain": uncertain,
        "hit_rate": hit_rate,
        "target_met": hit_rate >= 0.70,
    }


# =============================================================================
# 5. Hint Dependency 量化 (C 方向 Task 4)
# =============================================================================

# Hint Dependency 分级阈值
HINT_DEP_THRESHOLDS = {
    "low": (0.0, 0.25),      # 每 4 次练习才用 1 次提示
    "medium": (0.25, 0.50),   # 每 2-4 次练习用 1 次提示
    "high": (0.50, 1.0),      # 超过一半的练习需要提示
}

# 趋势判定阈值
TREND_THRESHOLD = 0.05  # score 变化 > 5% 视为有趋势


def compute_hint_dependency(
    total_hints: int,
    total_exercises: int,
    total_chat_messages: int = 0,
) -> dict:
    """
    基于实际行为数据量化提示依赖度。

    核心指标：hints_per_exercise = total_hints / (total_exercises + ε)
    辅助指标：chat_ratio = hints_via_chat / total_hints（聊天中索要提示的比例）

    参数:
        total_hints: 历史总提示使用次数
        total_exercises: 历史总练习次数
        total_chat_messages: 聊天消息总数（辅助计算 chat_ratio）

    返回:
        {
            "score": float,        # 0.0-1.0 依赖分数
            "label": str,          # "low" | "medium" | "high"
            "breakdown": {
                "hints_per_exercise": float,
                "hints_total": int,
                "exercises_total": int,
            }
        }
    """
    # 核心分数：hints / (exercises + hints)，范围 [0, 1]
    # 使用 hints/(exercises+hints) 而非 hints/exercises，避免 exercises=0 时的除零
    denom = total_exercises + total_hints
    if denom == 0:
        score = 0.0
    else:
        score = total_hints / denom



    # 确定 label
    if score <= HINT_DEP_THRESHOLDS["low"][1]:
        label = "low"
    elif score <= HINT_DEP_THRESHOLDS["medium"][1]:
        label = "medium"
    else:
        label = "high"

    return {
        "score": round(score, 3),
        "label": label,
        "breakdown": {
            "hints_per_exercise": round(score, 3),
            "hints_total": total_hints,
            "exercises_total": total_exercises,
        },
    }


def compute_hint_dependency_trend(
    current_label: str,
    previous_score: float,
    current_score: float,
) -> str:
    """
    判断提示依赖度的变化趋势。

    趋势判定：
    - "increasing": 依赖度上升（score 增加 > THRESHOLD）
    - "decreasing": 依赖度下降（score 减少 > THRESHOLD）
    - "stable": 变化在阈值内

    用于在教学策略中调整对待方式：
    - increasing → 降低提示等级，强制学生自己思考
    - decreasing → 说明学生在进步，可以保持
    - stable + high → 需要干预（陷入高依赖状态）
    """
    delta = current_score - previous_score

    if delta > TREND_THRESHOLD:
        return "increasing"
    elif delta < -TREND_THRESHOLD:
        return "decreasing"
    else:
        return "stable"


async def update_hint_dependency(
    db: AsyncSession,
    user_id: str,
    profile: "StudentProfile",
) -> dict:
    """
    从数据库更新用户的 hint_dependency 值。

    利用 StudentProfile 的计数器和 LearningEvent 历史计算真实依赖度。
    同时计算趋势（如果 profile 中有旧值）。

    参数:
        db: 数据库会话
        user_id: 用户 ID
        profile: 当前画像（用于比较趋势）

    返回:
        新的 hint_dependency dict: {"score": float, "label": str, "trend": str}
    """
    # 从画像统计获取基础数据
    total_hints = profile.total_hints_used
    total_exercises = profile.total_exercises_completed

    # 计算新分数
    result = compute_hint_dependency(total_hints, total_exercises)

    # 趋势分析
    trend = "stable"
    if profile.hint_dependency:
        # 尝试从已有 hint_dependency 字段解析旧分数
        # 格式可能是 {"score": 0.35, "label": "medium"} 或纯字符串 "low"
        prev_score = 0.0
        old_label = profile.hint_dependency
        try:
            old_data = json.loads(profile.hint_dependency)
            if isinstance(old_data, dict):
                prev_score = old_data.get("score", 0.0)
                old_label = old_data.get("label", "low")
        except (json.JSONDecodeError, TypeError):
            # 旧格式是纯字符串 "low"/"medium"/"high"
            prev_score = {"low": 0.1, "medium": 0.35, "high": 0.75}.get(
                str(profile.hint_dependency).lower(), 0.0
            )

        trend = compute_hint_dependency_trend(
            old_label, prev_score, result["score"]
        )

    # 将新结果写回 profile
    profile.hint_dependency = json.dumps({
        "score": result["score"],
        "label": result["label"],
    }, ensure_ascii=False)

    await db.commit()

    logger.info("hint_dependency_updated",
                user_id=user_id,
                score=result["score"],
                label=result["label"],
                trend=trend,
                hints=total_hints,
                exercises=total_exercises)

    return {
        "score": result["score"],
        "label": result["label"],
        "trend": trend,
        "breakdown": result["breakdown"],
    }
