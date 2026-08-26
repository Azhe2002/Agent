# 美食小助手 Agent

这是一个以“推荐中午吃什么，并给出做法”为统一任务的三分支对照学习项目。它强调先理解 Agent 的组成和验证方法，再学习框架。

> 当前状态：只有设计文档和目录骨架，没有业务代码、依赖清单或真实数据集。

## 三个学习分支

| 分支 | 学习重点 | 当前状态 |
|---|---|---|
| [branch-1-python-handwritten](branch-1-python-handwritten/README.md) | 手写 Agent Loop、工具调用协议、错误处理 | 待实现 |
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

## 目录说明

| 目录 | 内容 |
|---|---|
| `docs/` | 需求、架构、安全、路由、评测、路线图和 ADR |
| `datasets/` | 未来的菜谱与食材数据，格式规则见目录说明 |
| `evals/` | 跨分支共享评测用例和结果说明 |
| `shared/` | 共享契约、Prompt 版本和设计约束 |
| 三个 `branch-*` | 各实现分支的独立运行单元 |

## 配置边界

`.env.example` 只展示允许使用的变量名。复制出的本地 `.env` 已被 Git 忽略。不要把 `APIKEY/` 中的值复制进任何可提交文件。
