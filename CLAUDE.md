# 识图能力

遇到图片时，**不要用 Read 工具**，改用 vision.js：

```
node vision.js "<图片路径>" "用中文描述这张图片"
```

## 触发场景

- 用户发送图片（消息中出现图片路径或 ["Saved attachments:"]）
- 用户要求分析、描述、识别图片内容
- 看到 `[Unsupported Image]` 标记时，主动询问用户图片是否已保存到本地

## 用法

```
# 本地文件
node vision.js screenshot.png "用中文描述这张图片的内容"

# 网络 URL
node vision.js --url https://example.com/img.jpg "这是什么"
```

## 配置

- 服务：阿里云百炼千问 `qwen-vl-max`
- Key 已配置在项目 .env 中

---

# RAG / Embedding 架构

## 检索链路

```
用户问题
  → DashScope text-embedding-v3 API (语义向量, 1024维)
  → ChromaDB (余弦相似度检索)
  + TF-IDF 关键词检索 (内存, 服务重启自动重建)
  → 合并去重 (向量优先)
  → 注入 System Prompt → LLM 生成回复
```

## Embedding 服务

- 服务商：阿里云百炼 DashScope（OpenAI 兼容接口）
- 模型：`text-embedding-v3`（1024 维，中文 SOTA）
- Key：`DASHSCOPE_API_KEY`，配置在项目根目录 `.env`
- 接口：`POST https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings`
- 限制：每批最多 10 条文本
- 成本：~¥0.0007/千token

## 降级策略（三层防护）

1. DashScope API 正常 → 语义向量 + TF-IDF 混合检索
2. DashScope API 失败 → 自动降级到纯 TF-IDF 检索
3. TF-IDF 也失败 → 无 RAG 模式（基础对话照样正常）

## 配置项

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DASHSCOPE_API_KEY` | - | 阿里云百炼 API Key（必填） |
| `EMBEDDING_MODEL` | `text-embedding-v3` | Embedding 模型 |
| `DASHSCOPE_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | API 端点 |

## 常见问题

### AI 聊天卡住/超时
- 先检查 `DASHSCOPE_API_KEY` 是否正确配置
- 检查 ChromaDB collection 是否有数据（`vector_store.get_collection().count()`）
- 如果没有数据：`python -c "import asyncio; from app.database.session import AsyncSessionFactory; from app.services.rag_service import rebuild_index; ..."`
- 如果 API 不可达：自动降级到 TF-IDF，不影响聊天

### 重启后向量索引丢失
- TF-IDF 索引在 lifespan 启动时自动从 DB 重建
- ChromaDB 向量数据持久化在 `backend/chroma_db/` 目录
- 如果丢失：运行 `rebuild_index()` 重建
