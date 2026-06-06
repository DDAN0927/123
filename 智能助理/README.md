# 🤖 SmartPal - 自研 ReAct 多工具智能助手

> 一个能理解自然语言、自主调用工具、拥有记忆、支持 RAG 的个人 AI 助手
>
> **面试亮点：完全自研 ReAct 循环，不依赖 LangChain AgentExecutor**

---

## ✨ 核心特性

### 🌟 自研 ReAct 循环（面试必讲！）
- **不依赖 LangChain AgentExecutor**
- 完全自主实现的推理-行动-观察循环
- 使用正则表达式解析 LLM 输出
- 支持 5 轮迭代，每轮都有完整日志

### 🛠️ 8 个实用工具
| 工具 | 功能 |
|------|------|
| 🔍 search_web | 联网搜索实时信息 |
| 🌤️ get_weather | 查询实时天气 |
| ⏰ get_current_time | 获取当前时间 |
| 📐 calculate | 数学计算 |
| 📝 write_note | 保存笔记 |
| 📖 read_note | 读取笔记 |
| 🔔 add_reminder | 添加提醒事项 |
| 📋 list_reminders | 列出提醒 |

### 🧠 记忆系统
- 短期对话记忆（6 轮上下文）
- 长期向量记忆（Chromadb + HuggingFace Embeddings）

### 💬 流畅界面
- Streamlit 聊天 UI
- 支持多轮对话
- 流式体验

---

## 🏗️ 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        Streamlit UI                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              自研 ReAct 循环（核心！）                         │
│  ┌──────────┐    ┌──────────┐    ┌───────────────────────┐  │
│  │  Thought │───▶│  Action  │───▶│    Observation        │  │
│  └──────────┘    └──────────┘    └───────────────────────┘  │
│       │              │                        │               │
│       └──────────────┴────────────────────────┘               │
│                              │                                │
│                              ▼                                │
│                       Answer User                            │
└─────────────────────────────────────────────────────────────┘
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│   LLM (GPT-3.5) │   │   8 个工具      │   │    Memory       │
│   / DeepSeek    │   │                 │   │                 │
└─────────────────┘   └─────────────────┘   └─────────────────┘
```

---

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置 API Key
在 `.env` 文件中添加：
```env
OPENAI_API_KEY=你的-api-key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-turbo
SERPAPI_API_KEY=可选的-serpapi-key（用于网络搜索）
```

### 3. 运行项目
```bash
streamlit run app.py
```

访问 `http://localhost:8501` 开始使用！

---

## 📂 项目结构

```
SmartPal/
├── app.py                 # Streamlit UI 主入口
├── agent.py               # Agent 配置
├── react_agent.py         # 🔥 自研 ReAct 循环（核心）
├── tools.py               # 8 个工具定义
├── memory.py              # 记忆模块（短期 + 长期）
├── .env                   # 环境变量
├── requirements.txt       # 依赖列表
└── README.md              # 本文档
```

---

## 🔥 自研 ReAct 循环技术细节

### 核心原理
```python
while iteration < max_iterations:
    # 1. 构建提示词
    prompt = build_prompt(user_input, scratchpad)

    # 2. 调用 LLM
    llm_output = llm.invoke(prompt)

    # 3. 解析输出（正则表达式）
    parsed = parse_llm_output(llm_output)

    # 4. 判断下一步
    if has_answer:
        return answer
    elif has_action:
        observation = execute_tool(action)
        scratchpad += observation
```

### 解析策略
使用正则表达式匹配：
- `Answer: ...` → 直接回答用户
- `Thought: ...` → 推理过程
- `Action: ...` + `Action Input: {...}` → 工具调用

---

## 📊 成本优化（可选）

| 模型 | 费用（1M tokens） | 延迟 | 推荐场景 |
|------|-----------------|------|---------|
| qwen-turbo | ~¥0.3 | 低 | 日常对话 |
| qwen-plus | ~¥0.8 | 低 | 复杂任务 |
| DeepSeek | ~¥1 | 低 | 性价比选择 |

---

## 📝 License

MIT License - 自由使用，欢迎 fork！

---

**⭐ 如果这个项目对你有帮助，欢迎 star！**
