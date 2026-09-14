"""
TRAVER 离线评测台适配器 —— SRS 3.2 补充 §1 的落地实现

定位（要点，别搞错）
--------------------
TRAVER 在本项目里是 **离线评测台**，不是产品链路上的组件。它回答的问题是：
"PyTutor 的辅导，到底有没有把（模拟）学生教会？"——通过 前测 → 辅导对话 →
后测 + 代码生成测试，算出辅导成效率 TOR。

因此本文件位于 `evaluation/` 而非 `app/`，**不被任何请求路径 import**。
产品代码零改动，这是它相对其他方案最大的优势。

架构
----
    TRAVER 模拟学生引擎  ──调用──▶  TutorAgent 接口  ──HTTP──▶  PyTutor /api/v1/chat
                                        ▲
                                   我们只写这一层

诚实边界（写在最前面，因为它常被误读）
--------------------------------------
"换上 API key 就能跑"说的是 **TRAVER 自己的管线**。接到 PyTutor 上仍需要：
  1. 本适配器（把它的 tutor 调用协议翻成我们的 HTTP 接口）；
  2. **任务集核对**——这是被低估的一步。TRAVER 的前后测任务若偏英文、偏通用
     编程（而非 Python 初学者），TOR 数字算得出来但没有意义。必须先筛选或替换。
  3. API 预算——模拟学生是多次 LLM 调用，n 个学生 × m 轮对话 × k 个任务。

！！本地对齐点 ！！
------------------
`TutorAgent.respond()` 的**签名**取自 SRS 3.2 补充 §1.2 的设计稿，但 TRAVER
实际的 tutor 接口签名我无法核实（编写本文件时无网）。拿到仓库后：

    1. 打开其 `scripts/run/run_traver.sh` 找到 tutor 的注入点；
    2. 读那个内置 tutor 类的方法签名；
    3. 只改本文件 `TraverTutorShim` 一个类去适配它。

其余部分（HTTP 客户端、重试、会话隔离、成本计量）都与 TRAVER 无关，不必动。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol


# =============================================================================
# 1. 我们这一侧：稳定的、可单测的 tutor 客户端
# =============================================================================

@dataclass
class ChatTurn:
    role: str          # "student" | "tutor"
    content: str


@dataclass
class TutorCallStats:
    """成本计量。模拟学生评测最容易失控的就是 API 花费，默认就统计。"""
    calls: int = 0
    failures: int = 0
    total_latency_s: float = 0.0

    def record(self, latency: float, ok: bool) -> None:
        self.calls += 1
        self.total_latency_s += latency
        if not ok:
            self.failures += 1

    def summary(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "failures": self.failures,
            "avg_latency_s": round(self.total_latency_s / self.calls, 3) if self.calls else 0.0,
        }


class PyTutorTutorAgent:
    """把 PyTutor 的 /api/v1/chat 包装成一个可被外部引擎驱动的 tutor。

    设计约束：
      - 无状态。会话状态由调用方（TRAVER 学生引擎）持有的 dialog_history 携带，
        这样并发跑多个模拟学生时不会串台。
      - 失败不静默。LLM 超时/5xx 会重试；重试耗尽则抛出，因为把兜底回复
        混进 TOR 统计会污染结论（"教不会"和"服务挂了"必须区分）。
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout_s: float = 60.0,
        max_retries: int = 2,
        chat_path: str = "/api/v1/chat",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or os.environ.get("PYTUTOR_API_KEY", "")
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.chat_path = chat_path
        self.stats = TutorCallStats()

    def respond(
        self,
        dialog_history: list[dict[str, str]],
        student_utterance: str,
        task: dict[str, Any],
    ) -> str:
        payload = {
            "history": dialog_history,
            "message": student_utterance,
            "task": task,
            # 评测台标记：便于后端在日志里把评测流量与真实用户流量分开，
            # 也便于将来给评测流量单独限流。后端可忽略该字段。
            "eval_context": {"harness": "traver-dict"},
        }
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            t0 = time.monotonic()
            try:
                reply = self._post(self.chat_path, payload)
                self.stats.record(time.monotonic() - t0, ok=True)
                return self._extract_reply(reply)
            except Exception as e:  # noqa: BLE001
                self.stats.record(time.monotonic() - t0, ok=False)
                last_err = e
                if attempt < self.max_retries:
                    time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(
            f"PyTutor /chat 连续 {self.max_retries + 1} 次失败，中止本条评测："
            f"{last_err}. 不要用兜底文本顶替——那会把服务故障算成教学失败。"
        )

    # -- 内部 ---------------------------------------------------------------

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}),
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))

    @staticmethod
    def _extract_reply(resp: dict[str, Any]) -> str:
        """容忍后端返回结构的小差异；找不到就报错，不返回空串。"""
        for k in ("reply", "message", "content", "answer"):
            v = resp.get(k)
            if isinstance(v, str) and v.strip():
                return v
        # 有些实现把回复嵌在 data 里
        data = resp.get("data")
        if isinstance(data, dict):
            for k in ("reply", "message", "content"):
                v = data.get(k)
                if isinstance(v, str) and v.strip():
                    return v
        raise ValueError(f"无法从 /chat 响应中取出回复文本：keys={list(resp)}")


# =============================================================================
# 2. TRAVER 侧接缝：唯一需要按其真实接口改的地方
# =============================================================================

class TraverTutorProtocol(Protocol):
    """TRAVER 内置 tutor 的（推测的）接口。拿到仓库后按实际改。"""

    def generate(self, history: list[dict], utterance: str, task: dict) -> str: ...


class TraverTutorShim:
    """>>> 本地对齐点 <<<

    TRAVER 的学生引擎会以某个签名调用 tutor。我们不知道那个签名的确切形状，
    所以把翻译集中在这里：把它的调用形状适配到 PyTutorTutorAgent.respond()。

    典型需要改的三件事：
      - 方法名（generate / __call__ / respond / chat）
      - history 里每一项的键名（role/content vs speaker/text）
      - task 字典的字段（题面在 prompt 还是 description）
    """

    def __init__(self, agent: PyTutorTutorAgent):
        self.agent = agent

    # 覆盖面：把常见的几种调用形状都接上，减少你改代码的概率
    def generate(self, history: list[dict], utterance: str, task: dict) -> str:
        return self.agent.respond(self._norm_history(history), utterance, task)

    def respond(self, history: list[dict], utterance: str, task: dict) -> str:
        return self.generate(history, utterance, task)

    def __call__(self, history: list[dict], utterance: str, task: dict) -> str:
        return self.generate(history, utterance, task)

    @staticmethod
    def _norm_history(history: list[dict]) -> list[dict[str, str]]:
        """把 TRAVER 的 history 项归一成 {role, content}。"""
        out = []
        for h in history or []:
            role = h.get("role") or h.get("speaker") or h.get("from") or "student"
            content = h.get("content") or h.get("text") or h.get("message") or ""
            role = "tutor" if role.lower() in {"tutor", "teacher", "assistant"} else "student"
            out.append({"role": role, "content": content})
        return out


# =============================================================================
# 3. 任务集核对 —— 被低估但必须做的一步
# =============================================================================

@dataclass
class TaskAudit:
    total: int = 0
    python: int = 0
    non_python: int = 0
    likely_beginner: int = 0
    flagged: list[str] = field(default_factory=list)

    def report(self) -> str:
        keep = self.likely_beginner
        return (
            f"任务集：{self.total} 条，其中 Python {self.python}、非 Python {self.non_python}；"
            f"疑似初学者难度 {keep} 条。"
            + ("\n需人工复核：\n  - " + "\n  - ".join(self.flagged[:10]) if self.flagged else "")
        )


# 出现这些词，多半超出"Python 初学者"范围，需人工复核是否保留
_ADVANCED_MARKERS = (
    "asyncio", "metaclass", "decorator", "generator", "yield", "threading",
    "multiprocessing", "numpy", "pandas", "regex", "socket", "dynamic programming",
)


def audit_task_set(tasks: list[dict[str, Any]]) -> TaskAudit:
    """在跑 TOR 之前，先确认任务落在 Python 初学者范围内。

    这不是形式主义：如果任务偏难或偏英文，模拟学生前测就全错、后测还是全错，
    TOR 会算出一个"辅导无效"的数字，而真实原因是任务选错了。
    """
    a = TaskAudit(total=len(tasks))
    for t in tasks:
        lang = str(t.get("language", "python")).lower()
        text = " ".join(str(t.get(k, "")) for k in ("prompt", "description", "title")).lower()
        if lang != "python":
            a.non_python += 1
            continue
        a.python += 1
        hits = [m for m in _ADVANCED_MARKERS if m in text]
        if hits:
            a.flagged.append(f"{t.get('id', '?')}: 含 {', '.join(hits[:3])}")
        else:
            a.likely_beginner += 1
    return a


if __name__ == "__main__":
    # 自检：不联网，只验证 shim 的形状转换与任务审计逻辑
    tasks = [
        {"id": "t1", "language": "python", "prompt": "写一个函数返回列表最大值"},
        {"id": "t2", "language": "python", "prompt": "用 asyncio 实现并发爬虫"},
        {"id": "t3", "language": "java", "prompt": "..."},
    ]
    print(audit_task_set(tasks).report())

    hist = [{"speaker": "teacher", "text": "你觉得这里为什么报错？"}]
    print("\nhistory 归一化 →", TraverTutorShim._norm_history(hist))
