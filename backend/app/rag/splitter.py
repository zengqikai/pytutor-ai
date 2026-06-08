"""
文档切分器
=========

将长篇 Markdown 文档切分成适合检索的小片段（chunk）。

切分策略：
    按 Markdown 标题层级切分（## 和 ###），
    每个章节成为一个独立 chunk。
    如果章节太长（> 2000 字符），再按段落切分。

为什么按标题切分？
    - 每个 chunk 有独立的语义主题（一个知识点）
    - 检索时能精确定位到相关章节
    - 标题作为 chunk 的 heading 元数据，提升检索准确性

为什么不是固定长度切分？
    - 固定长度可能在句子中间断开，破坏语义
    - Markdown 文档本身按标题组织，天然适合按章节切分
"""

import re
from typing import Optional


# 最大 chunk 大小（字符数）
MAX_CHUNK_SIZE = 2000
# 最小 chunk 大小（太小的 chunk 合并到上一个）
MIN_CHUNK_SIZE = 100


def split_markdown(content: str, title: str = "") -> list[dict]:
    """
    将 Markdown 内容切分为 chunk 列表。

    切分逻辑：
    1. 找到所有 ## 标题作为分段点
    2. 每个 ## 段内再按 ### 细分
    3. 超过 MAX_CHUNK_SIZE 的段落进一步按空行切分
    4. 太短的 chunk 合并

    参数:
        content: Markdown 格式的文本
        title: 文档标题

    返回:
        list[dict]: 每个 chunk 含 {content, heading, chunk_index}
    """
    chunks = []

    # 第一步：按 ## 标题分段
    # 正则 (?=^## ) 表示在 ## 之前分割（保留分隔符）
    sections = re.split(r"(?=^## )", content, flags=re.MULTILINE)

    chunk_index = 0

    for section in sections:
        if not section.strip():
            continue

        # 提取 ## 标题
        heading_match = re.match(r"^## (.+)$", section, re.MULTILINE)
        section_heading = heading_match.group(1).strip() if heading_match else title

        # 第二步：按 ### 标题分子段
        subsections = re.split(r"(?=^### )", section, flags=re.MULTILINE)

        for sub in subsections:
            if not sub.strip():
                continue

            # 提取 ### 标题（如果有）
            sub_heading_match = re.match(r"^### (.+)$", sub, re.MULTILINE)
            if sub_heading_match:
                sub_heading = f"{section_heading} > {sub_heading_match.group(1).strip()}"
            else:
                sub_heading = section_heading

            # 第三步：如果子段太长，按空行再切分
            if len(sub) > MAX_CHUNK_SIZE:
                paragraphs = sub.split("\n\n")
                current_chunk = ""
                for para in paragraphs:
                    if len(current_chunk) + len(para) > MAX_CHUNK_SIZE and len(current_chunk) >= MIN_CHUNK_SIZE:
                        chunks.append({
                            "content": current_chunk.strip(),
                            "heading": sub_heading,
                            "chunk_index": chunk_index,
                        })
                        chunk_index += 1
                        current_chunk = para
                    else:
                        current_chunk += "\n\n" + para if current_chunk else para

                if current_chunk.strip():
                    chunks.append({
                        "content": current_chunk.strip(),
                        "heading": sub_heading,
                        "chunk_index": chunk_index,
                    })
                    chunk_index += 1
            else:
                if sub.strip():
                    chunks.append({
                        "content": sub.strip(),
                        "heading": sub_heading,
                        "chunk_index": chunk_index,
                    })
                    chunk_index += 1

    # 第四步：合并太短的 chunk 到前一个
    merged = []
    for chunk in chunks:
        if len(chunk["content"]) < MIN_CHUNK_SIZE and merged:
            merged[-1]["content"] += "\n" + chunk["content"]
        else:
            merged.append(chunk)

    # 重新编号
    for i, chunk in enumerate(merged):
        chunk["chunk_index"] = i

    return merged


def simple_tokenize(text: str) -> list[str]:
    """
    简单的中英文混合分词。

    用于 TF-IDF 关键词检索。
    不是完整的分词器，但足够 MVP 使用。

    分词策略：
    - 提取中文 2-gram（两个连续的汉字）
    - 提取英文单词（连续字母，3 字符以上）
    - Python 标识符（含下划线）
    """
    tokens = []

    # 提取 Python 标识符和代码（反引号内容）
    code_pattern = re.compile(r"`([^`]+)`")
    for match in code_pattern.finditer(text):
        code = match.group(1)
        # 提取代码中的标识符
        identifiers = re.findall(r"[a-zA-Z_]\w+", code)
        tokens.extend(id.lower() for id in identifiers if len(id) >= 2)

    # 移除代码块后提取普通文本
    text_no_code = code_pattern.sub(" ", text)

    # 提取英文单词（连续字母，3 字符以上）
    english_words = re.findall(r"[a-zA-Z]{3,}", text_no_code)
    tokens.extend(w.lower() for w in english_words)

    # 提取中文 2-gram（两个连续汉字）
    chinese_chars = re.findall(r"[一-鿿]", text_no_code)
    for i in range(len(chinese_chars) - 1):
        tokens.append(chinese_chars[i] + chinese_chars[i + 1])

    # 去重并保持顺序
    seen = set()
    unique_tokens = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            unique_tokens.append(t)

    return unique_tokens
