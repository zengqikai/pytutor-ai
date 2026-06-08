"""
聊天 API 端到端测试
==================

用 httpx 直接调 API（绕过 curl 的编码问题）。
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

BASE_URL = "http://localhost:8000/api/v1"


async def test_chat_flow():
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. 注册
        print("===== 1. 注册 =====")
        reg_resp = await client.post(f"{BASE_URL}/auth/register", json={
            "email": "chat_test2@example.com",
            "password": "testpass123",
            "display_name": "Chat Test 2",
        })
        reg_data = reg_resp.json()
        token = reg_data["token"]["access_token"]
        print(f"User ID: {reg_data['user']['id']}")
        print(f"Token: {token[:40]}...")

        headers = {"Authorization": f"Bearer {token}"}

        # 2. 创建会话
        print("\n===== 2. 创建会话 =====")
        session_resp = await client.post(
            f"{BASE_URL}/chat/sessions",
            json={"title": "学习 Python 基础"},
            headers=headers,
        )
        session_data = session_resp.json()
        session_id = session_data["id"]
        print(f"Session ID: {session_id}")
        print(f"Title: {session_data['title']}")

        # 3. 发送概念问题
        print("\n===== 3. 发送概念问题 =====")
        msg_resp = await client.post(
            f"{BASE_URL}/chat/sessions/{session_id}/messages",
            json={"content": "什么是 Python 中的列表（list）？请用简单的话解释。"},
            headers=headers,
        )
        msg_data = msg_resp.json()
        ai = msg_data["ai_response"]
        print(f"回复类型: {ai['response_type']}")
        print(f"提示等级: {ai['hint_level']}")
        print(f"关联知识点: {ai['related_concepts']}")
        print(f"建议下一步: {ai['next_action']}")
        print(f"回复内容:\n{ai['message'][:400]}...")

        # 4. 获取会话历史
        print("\n===== 4. 获取会话历史 =====")
        hist_resp = await client.get(
            f"{BASE_URL}/chat/sessions/{session_id}",
            headers=headers,
        )
        hist_data = hist_resp.json()
        print(f"消息总数: {len(hist_data['messages'])}")

        # 5. 获取会话列表
        print("\n===== 5. 获取会话列表 =====")
        list_resp = await client.get(
            f"{BASE_URL}/chat/sessions",
            headers=headers,
        )
        sessions = list_resp.json()
        print(f"会话数量: {len(sessions)}")
        for s in sessions:
            print(f"  - {s['title']} ({s['message_count']} 条消息)")

        print("\n===== 全部测试通过! =====")


if __name__ == "__main__":
    asyncio.run(test_chat_flow())
