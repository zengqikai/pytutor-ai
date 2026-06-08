"""
Agent 状态定义
==============

LangGraph 的 State 是所有节点共享的数据结构。
每个节点读取 State → 处理 → 返回 State 的更新部分。

设计原则：
    State 应该是"单页仪表盘"——一眼就能看到 Agent 的当前状态：
    什么输入 → 什么意图 → 检索到什么 → 生成了什么 → 是否安全 → 是否有错
"""

from typing import Annotated, Any, Literal, Optional, Sequence
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    Agent 工作流的共享状态。

    每个键的含义：
        messages:         对话历史（LangGraph 会自动管理消息追加）
        user_input:       当前用户输入（原始文本）
        intent:           识别出的意图
        intent_confidence: 意图识别的置信度 0-1
        rag_context:      检索到的知识上下文
        safety_result:    安全检查结果 "pass" | "block" | "warn"
        safety_reason:    安全检查拦截原因
        code_to_execute:  待执行的代码（从用户消息中提取）
        code_result:      代码执行结果
        tutor_response:   AI 导师的结构化回复
        is_valid_output:  输出是否通过校验
        error:            错误信息（如有）
        current_step:     当前步骤（用于追踪和日志）
    """
    # 消息历史（add_messages reducer 自动合并新消息）
    messages: Annotated[Sequence[dict], add_messages]

    # 用户输入
    user_input: str

    # 意图识别
    intent: str  # concept_question | code_debug | exercise_request | general | unsafe
    intent_confidence: float

    # RAG 检索结果
    rag_context: Optional[str]

    # 安全检查
    safety_result: str  # pass | block | warn
    safety_reason: str

    # 代码执行
    code_to_execute: Optional[str]
    code_result: Optional[dict]

    # AI 回复
    tutor_response: Optional[dict]

    # 输出校验
    is_valid_output: bool

    # 错误追踪
    error: Optional[str]
    current_step: str
