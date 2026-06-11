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
