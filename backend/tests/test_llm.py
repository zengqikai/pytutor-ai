"""
LLM 服务测试脚本
================

验证 DeepSeek API 调用是否正常工作。

使用方法：
    1. 在 .env 中填入真实的 DEEPSEEK_API_KEY
    2. 运行: python tests/test_llm.py

如果 API Key 未配置，测试会跳过。
"""

import asyncio
import sys
from pathlib import Path

# 确保 backend/ 在 Python 路径中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.schemas.ai import ChatMessage
from app.services.llm_service import chat_completion


async def test_basic_chat():
    """测试基本对话功能。"""
    print(f"模型: {settings.deepseek_model}")
    print(f"API Key 前缀: {settings.deepseek_api_key[:10]}...")

    if "placeholder" in settings.deepseek_api_key.lower():
        print("\n[警告] API Key 尚未配置！请在 .env 中设置 DEEPSEEK_API_KEY 后再测试。")
        print("   获取 Key: https://platform.deepseek.com")
        return

    try:
        response = await chat_completion(
            messages=[
                ChatMessage(
                    role="system",
                    content="你是一个 Python 编程导师。用中文回答，简洁明了。",
                ),
                ChatMessage(
                    role="user",
                    content="请用一句话解释 Python 中的 for 循环。",
                ),
            ],
        )
        print(f"\n[成功] LLM 调用成功!")
        print(f"   模型: {response.model}")
        print(f"   回复: {response.content}")
        print(f"   Token: 输入={response.usage.prompt_tokens}, "
              f"输出={response.usage.completion_tokens}, "
              f"总计={response.usage.total_tokens}")
        print(f"   结束原因: {response.finish_reason}")
    except Exception as e:
        print(f"\n[失败] LLM 调用失败: {e}")


if __name__ == "__main__":
    asyncio.run(test_basic_chat())
