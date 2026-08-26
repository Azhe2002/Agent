# 美食小助手 Agent —— 三分支对照学习项目（方案）

> 项目状态（2026-08-25）：已建立文档与目录骨架，尚未编写业务代码。项目入口见 [FoodAssistant/README.md](FoodAssistant/README.md)。密钥与 GitHub 安全规则见 [SECURITY.md](SECURITY.md)。

> 设计补充：默认供应商为 NVIDIA；MiMo、DeepSeek、Kimi 作为可配置候选。任何可能产生费用的自动回退默认关闭，模型 ID 与费用信息不写死在代码或共享契约中。

## Context

在本地实践一个 Agent 项目：「推荐中午吃什么 + 如何做菜」的美食小助手。
- **模型接入**：DeepSeek API（OpenAI 兼容，支持 Function Calling，便宜，无需翻墙）
- **学习诉求**：不设限单一技术栈，做 **3 个分支**对照学习 Agent 实现方式
- **环境**：Windows 11，Python 3.12 ✓，Node 24 ✓

目标：搭出同一款 Agent 的 3 种实现，共享数据集与工具设计，让用户对比「手写 Agent Loop vs 框架编排 vs 另一语言生态」，并顺带实践 RAG 检索。

## 项目结构

新建目录 `f:\Agent\FoodAssistant\`：

```
FoodAssistant\
├── README.md                    # 三分支总览 + 运行方法 + 对照学习点
├── datasets\
│   ├── recipes.json             # 25+ 道中文家常菜（名称/食材/步骤/耗时/口味/适合天气）
│   └── ingredients.json         # 常用食材清单（模拟"家里有什么"）
├── branch-1-python-handwritten\   # 分支1：Python 手写 Agent Loop（最底层）
│   ├── .env.example
│   ├── requirements.txt         # openai, python-dotenv
│   ├── agent.py                 # 手写 Agent 循环 + Function Calling 解析
│   ├── tools.py                 # 工具注册表 + 从零实现的检索
│   └── main.py                  # CLI 入口
├── branch-2-python-langgraph\     # 分支2：Python + LangGraph（框架编排）
│   ├── .env.example
│   ├── requirements.txt         # langgraph, langchain-openai, python-dotenv
│   ├── graph.py                 # 状态图：Agent 节点 + 工具节点 + 条件边
│   ├── tools.py                 # 同分支1的工具（框架版调用）
│   └── main.py
└── branch-3-typescript\           # 分支3：TypeScript（JS 生态）
    ├── .env.example
    ├── package.json             # openai, dotenv, typescript, tsx
    ├── tsconfig.json
    └── src\
        ├── agent.ts             # TS 手写 Agent Loop（与分支1对照）
        ├── tools.ts
        └── main.ts
```
### 可以实现按付费选择 默认免费NVIDIA api 然后是较低的mimo v2.5 deepseek-v4-flash 最后是最贵的kimi k2.5

## 核心设计（三分支统一，便于对照）

### DeepSeek 接入 其他的类似
- `base_url = https://api.deepseek.com`，`model = deepseek-chat`（支持 function calling）
- 用官方 OpenAI SDK（Python 版 / npm 版），API Key 从 `.env` 读取，`.gitignore` 排除
- 三个 `.env.example` 都放 `DEEPSEEK_API_KEY=`

### 工具（三分支同一套，4 个）
1. `get_weather(city)` — **mock** 天气/温度（注释说明如何换成真实天气 API）
2. `get_available_ingredients()` — 返回食材清单（模拟冰箱库存）
3. `search_recipes(keywords)` — 从菜谱库检索匹配菜（**RAG 教学点**）
4. `get_recipe(name)` — 返回某道菜完整做法

### Agent Loop
- **分支1 / 分支3（手写）**：`while` 循环调用 LLM → 有 `tool_calls` 就执行工具、把结果作为 tool 消息追加 → 无工具调用则输出最终回答。展示 Function Calling 协议的完整细节。
- **分支2（LangGraph）**：状态图——`agent` 节点（调模型）→ 条件边判断是否有工具调用 → `tools` 节点执行 → 回到 `agent`。展示框架如何把循环抽象成图。

### RAG 检索教学点
- 分支1/3 的 `search_recipes`：**从零实现**「字符级 n-gram + 余弦相似度」检索，无额外依赖、无需 embedding 模型，演示检索原理。
- 分支2：用 LangChain 检索器流程演示框架抽象。
- README 注明：真实项目会换 embedding 模型（如 bge-m3）做语义向量检索。

## 关键文件说明

- `datasets/recipes.json`：手写 25 道中文家常菜，字段含 `name, ingredients, steps, cook_time_minutes, flavor, suitable_weather, difficulty`
- `branch-1-python-handwritten/agent.py`：核心教学文件，含详细中文注释，标注每一步对应知识大纲里的哪个概念
- `branch-2-python-langgraph/graph.py`：LangGraph StateGraph + 条件边，对比手写循环
- `branch-3-typescript/src/agent.ts`：与分支1 1:1 对照的 TS 版本

## 验证方式

1. 三个分支都无 key 启动时给友好报错提示
2. 每个分支导出 `DEEPSEEK_API_KEY` 后运行：
   - 分支1/2：`python main.py "今天下雨有点冷，中午想吃点暖和的，家里有土豆胡萝卜"`
   - 分支3：`npx tsx src/main.ts "同上问题"`
3. 期望行为：Agent 依次调用 `get_weather` → `get_available_ingredients` → `search_recipes`，最终推荐一道菜并输出完整做法
4. 打印每次 LLM 调用/工具调用的日志，方便观察 Agent Loop
5. 交叉验证：同一问题三分支结果应一致（工具逻辑相同、仅实现不同）

## 备注

- 不引入 Chroma/FAISS 等重依赖，保持轻量、零编译、开箱即跑
- 所有分支代码带教学注释，README 列出「同一 Agent 三种写法的对照点」
- Key 只存 `.env`，不进代码
