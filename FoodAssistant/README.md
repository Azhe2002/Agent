# 美食小助手 Agent

这是一个以“推荐中午吃什么，并给出做法”为统一任务的三分支对照学习项目。它强调先理解 Agent 的组成和验证方法，再学习框架。

> 当前状态：分支 1 已具备命令行入口、本地 Web 快速测试台、四供应商显式切换、25 道原创教学菜谱和离线测试；分支 2、3 尚未实现。

## 三个学习分支

| 分支 | 学习重点 | 当前状态 |
|---|---|---|
| [branch-1-python-handwritten](branch-1-python-handwritten/README.md) | 手写 Agent Loop、工具调用协议、错误处理 | CLI 与本地 Web 已实现 |
| [branch-2-python-langgraph](branch-2-python-langgraph/README.md) | 状态图、节点、条件边、持久化 | 待实现 |
| [branch-3-typescript](branch-3-typescript/README.md) | TypeScript SDK、类型约束、与分支 1 对照 | 待实现 |

## 先读这些文档

1. [需求与验收](docs/requirements.md)
2. [系统架构](docs/architecture.md)
3. [共享工具契约](shared/contracts/tools.md)
4. [模型供应商与费用策略](docs/provider-routing.md)
5. [安全设计](docs/security.md)
6. [评测方案](docs/evaluation.md)
7. [实现路线图](docs/roadmap.md)

## 设计原则

- 三个分支共享相同的场景、数据、工具语义和评测集。
- 每个分支只改变实现方式，避免把语言、框架、模型和数据同时变化。
- 默认使用 NVIDIA 供应商配置；任何可能产生费用的回退必须显式开启。
- 工具先采用本地只读 Mock，理解闭环后再接真实服务。
- 先验证任务是否完成，再比较响应质量、延迟、调用次数和成本。

## 快速验证分支 1

先参考 `.env.example` 配置至少一个供应商，然后在仓库根目录启动本地测试台：

```powershell
& 'D:\Program Files\Python312\python.exe' FoodAssistant\branch-1-python-handwritten\web\server.py
```

浏览器打开 `http://127.0.0.1:8000`。页面可以逐请求显式选择 DeepSeek V4 Flash、MiMo V2.5、Kimi K2.6 或 NVIDIA GPT-OSS 20B，并显示实际调用的供应商和模型。未配置项会被禁用，失败时不会自动切换供应商。

实现阅读顺序、接口流程和测试说明见 [分支 1 代码学习指南](branch-1-python-handwritten/KNOWLEDGE.md)。

## 目录说明

| 目录 | 内容 |
|---|---|
| `docs/` | 需求、架构、安全、路由、评测、路线图和 ADR |
| `datasets/` | 25 道原创教学菜谱、模拟库存与数据来源说明 |
| `evals/` | 跨分支共享评测用例和结果说明 |
| `shared/` | 共享契约、Prompt 版本和设计约束 |
| 三个 `branch-*` | 各实现分支的独立运行单元 |

## 配置边界

`.env.example` 只展示允许使用的变量名。复制出的本地 `.env` 已被 Git 忽略。不要把 `APIKEY/` 中的值复制进任何可提交文件。
