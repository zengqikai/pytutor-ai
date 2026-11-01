"""
回复审核的失败处理与修订后再审核
================================

对应任务 08 的验收点：
- 审核调用失败时不能伪造及格分（返回 score=0 + review_available=False）
- 修订后的质量分必须来自对修订稿的实际审核，不能写死
- 审核要拿到真实的误区 ID，而不是 None
"""

import pytest

from app.core.config import settings
from app.services import pedagogy_service, tutor_service


class _Resp:
    def __init__(self, content: str):
        self.content = content


@pytest.fixture(autouse=True)
def _judge_off(monkeypatch):
    """这些用例针对单评委模式；Multi-Judge 有自己的测试。"""
    monkeypatch.setattr(settings, "ENABLE_MULTI_JUDGE", False)


async def test_judge_failure_is_not_scored(monkeypatch):
    async def boom(*a, **kw):
        raise RuntimeError("upstream 502")

    monkeypatch.setattr("app.services.llm_service.chat_completion", boom)
    result = await pedagogy_service.verify_response("回复正文", 2, "M3")

    assert result["score"] == 0
    assert result["review_available"] is False


async def test_unparseable_judge_output_is_not_scored(monkeypatch):
    async def garbage(*a, **kw):
        return _Resp("我觉得挺好的")

    monkeypatch.setattr("app.services.llm_service.chat_completion", garbage)
    result = await pedagogy_service.verify_response("回复正文", 2, "M3")

    assert result["score"] == 0
    assert result["review_available"] is False


async def test_valid_judge_output_kept(monkeypatch):
    async def ok(*a, **kw):
        return _Resp('{"is_valid": false, "score": 2, "issues": ["太长"], "needs_revision": true}')

    monkeypatch.setattr("app.services.llm_service.chat_completion", ok)
    result = await pedagogy_service.verify_response("回复正文", 2, "M3")

    assert result["score"] == 2
    assert result["needs_revision"] is True


async def test_revision_is_re_reviewed(monkeypatch):
    """第一稿不合格 → 重写 → 分数取自对重写稿的第二次审核。"""
    calls = {"llm": 0, "verify": []}

    async def fake_llm(messages, temperature=None, model=None):
        calls["llm"] += 1
        if calls["llm"] == 1:
            return _Resp("<!-- hint:2 -->第一稿：直接给出完整答案")
        return _Resp("<!-- hint:2 -->第二稿：先问你一个引导问题")

    async def fake_verify(text, level, mc_id):
        calls["verify"].append((text, level, mc_id))
        if text.startswith("第一稿"):
            return {"is_valid": False, "score": 2, "issues": ["泄露答案"], "needs_revision": True}
        return {"is_valid": True, "score": 4, "issues": [], "needs_revision": False}

    monkeypatch.setattr(tutor_service, "_llm_chat", fake_llm)
    monkeypatch.setattr(pedagogy_service, "verify_response", fake_verify)

    resp = await tutor_service.generate_tutor_response(
        user_message="为什么 new = items.append(5) 之后 new 是 None？",
        conversation_history=[],
        misconception_id="M3",
    )

    assert calls["llm"] == 2
    assert len(calls["verify"]) == 2
    # 两次审核都必须拿到真实误区与本次提示等级
    assert all(mc == "M3" for _, _, mc in calls["verify"])
    # 最终分数来自修订稿的实际审核，而不是写死的 2
    assert resp.verify_score == 4
    assert "第二稿" in resp.message


async def test_revision_review_failure_marks_unreviewed(monkeypatch):
    calls = {"llm": 0}

    async def fake_llm(messages, temperature=None, model=None):
        calls["llm"] += 1
        return _Resp("<!-- hint:2 -->又一稿")

    async def flaky_verify(text, level, mc_id):
        if "第一稿" in text or calls["llm"] == 1:
            return {"is_valid": False, "score": 2, "issues": [], "needs_revision": True}
        raise RuntimeError("judge down")

    monkeypatch.setattr(tutor_service, "_llm_chat", fake_llm)
    monkeypatch.setattr(pedagogy_service, "verify_response", flaky_verify)

    resp = await tutor_service.generate_tutor_response(
        user_message="什么是 for 循环",
        conversation_history=[],
        misconception_id=None,
    )
    # 复审失败 → 未复核（None），不能落成 2 分
    assert resp.verify_score is None
