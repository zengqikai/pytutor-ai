"""
文档加载器
=========

从不同来源加载教学内容：
- Markdown 文件（用于初始知识库）
- 纯文本
- JSON（后续支持）

原理：
    统一将不同格式的输入转为"标题 + 内容"的结构，
    方便后续的 splitter 统一处理。
"""

import re
from pathlib import Path


def load_markdown_file(file_path: str | Path) -> dict:
    """
    加载单个 Markdown 文件。

    返回:
        dict: {"title": str, "content": str}

    自动提取：
    - 第一个 # 标题作为文档标题
    - 完整 Markdown 内容
    """
    path = Path(file_path)
    content = path.read_text(encoding="utf-8")

    # 提取文档标题（第一个 # 标题）
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem

    return {
        "title": title,
        "content": content,
    }


def load_markdown_directory(dir_path: str | Path) -> list[dict]:
    """
    加载目录下的所有 Markdown 文件。

    用法:
        docs = load_markdown_directory("knowledge/")
        for doc in docs:
            await rag_service.ingest_document(doc["title"], doc["content"])
    """
    path = Path(dir_path)
    documents = []

    for md_file in sorted(path.glob("*.md")):
        try:
            doc = load_markdown_file(md_file)
            documents.append(doc)
        except Exception as e:
            print(f"[WARN] 加载失败: {md_file}: {e}")

    return documents


def load_text(title: str, content: str) -> dict:
    """加载纯文本内容为文档格式。"""
    return {"title": title, "content": content}
