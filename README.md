# Personal Agent

> 这是一个基于 LLM 的个人情感陪伴 Agent，具备长期记忆与个性化交互能力。当前已完成 **第二阶段：长期记忆强化** 开发。

## 核心功能

- **深度对话**：集成 DeepSeek-V3 模型，支持流利自然的情感交互。
- **智能记忆系统**（阶段2升级）：
  - **短期记忆**：Redis 缓存实时会话上下文。
  - **长期记忆**：ChromaDB 向量数据库存储历史对话片段。
  - **分层摘要**：
    - **周摘要** (L1)：DeepSeek-V3 自动提炼本周要点。
    - **月/年摘要** (L2/L3)：**DeepSeek-R1 (Reasoner)** 深度思考模型生成人生档案。
  - **混合检索**：结合向量语义、时间线（"上周"、"去年"）与实体关联的多维检索策略。
- **动态人设**：支持通过 `prompt.yaml` 实时调整 System Prompt。
- **交互体验**：
  - **拟人化回复**：消息自动分段，模拟打字节奏。
  - **回忆感知**：新增 "她正在回忆..." 动态状态，展示 AI 思考与检索过程。
  - **双端打断**：支持随时打断与多条消息暂存。
  - **亮/暗模式**：一键切换界面主题。
- **精致 UI**：Mobile-First 的 Glassmorphism 设计。

## 快速启动

### 1. 环境准备

确保已安装 Python 3.9+，并**运行 Redis 服务**。（请运行/redis/start.bat）

```bash
# 激活环境 (如果使用 Conda)
conda activate personalAgent

# 安装依赖 (新增 apscheduler)
pip install -r requirements.txt
```

### 2. 配置

1.  在根目录打开 `api_key.json`，填入你的 DeepSeek API Key。
2.  (可选) 在 `prompt.yaml` 中调整人设配置。
3.  (可选) 将自定义头像放入 `app/static/` 目录（命名为 `ai_avatar.jpg/png`）。

### 3. 运行

```bash
python main.py
```

启动后访问：`http://localhost:8000`

> **注意**：
> 1. 自动摘要任务将在后台定时运行（默认每周日凌晨）。
> 2. 系统会在启动时自动检查停机期间是否错过了摘要时间，并进行补漏处理。

## 协议

MIT License
