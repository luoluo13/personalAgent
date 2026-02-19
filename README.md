# Personal Agent

> 这是一个基于 LLM 的个人情感陪伴 Agent，具备长期记忆与个性化交互能力。当前为第一阶段MVP开发。

## 核心功能

- **深度对话**：集成 DeepSeek-V3 模型，支持流利自然的情感交互。
- **记忆系统**：
  - **短期记忆**：Redis 缓存会话上下文。
  - **长期记忆**：ChromaDB 向量数据库存储历史对话片段。
  - **结构化存储**：SQLite 记录用户与会话元数据。
- **动态人设**：支持通过 `prompt.yaml` 实时调整 System Prompt（支持多行文本）。
- **智能交互**：
  - **拟人化回复**：AI 消息自动分段显示，模拟真人打字节奏与多气泡连续发送。
  - **双端打断**：支持随时打断 AI 发言，支持用户多条消息暂存合并发送。
  - **亮/暗模式**：一键切换界面主题，自动适配系统风格。
- **精致 UI**：Mobile-First 的 Glassmorphism 设计，提供流畅的沉浸式体验。

## 快速启动

### 1. 环境准备

确保已安装 Python 3.9+，并**运行 Redis 服务**。（请运行/redis/start.bat）

```bash
# 安装依赖
pip install -r requirements.txt
```

### 2. 配置

1.  在根目录打开 `api_key.json`，填入你的 DeepSeek API Key。
2.  (可选) 在 `prompt.yaml` 中调整人设配置（支持多行、特殊字符）。
3.  (可选) 将自定义头像放入 `app/static/` 目录（命名为 `ai_avatar.jpg/png`）。

### 3. 运行

```bash
python main.py
```

启动后访问：`http://localhost:8000`

## 协议

MIT License

Copyright (c) 2026 Personal Agent Project

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
