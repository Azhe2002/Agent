# Agent 入门学习仓库

这是一个面向 Agent 开发初学者的学习与设计仓库。当前主项目是“美食小助手 Agent”，目标是用同一需求对照学习手写 Agent Loop、LangGraph 编排和 TypeScript 实现。

> 当前阶段：**设计与目录骨架已建立，尚未编写业务代码。**

## 安全红线

- `APIKEY/` 是仅限本机使用的敏感目录，已被 `.gitignore` 整体排除。
- 不在 Markdown、源代码、日志、截图、Issue、提交信息中粘贴真实密钥。
- 可提交的 `.env.example` 只能保留变量名，值必须为空。
- 如果密钥曾进入 Git 历史，应立即撤销并轮换；仅删除文件并不能消除历史泄漏。

详细规则见 [SECURITY.md](SECURITY.md) 和 [AGENTS.md](AGENTS.md)。

## 仓库导航

| 路径 | 用途 |
|---|---|
| [Plan.md](Plan.md) | 原始项目设想与三分支方案 |
| [Knowledge.md](Knowledge.md) | 从企业岗位资料整理的 Agent 知识索引 |
| `Agent/`、`Harness/`、`Infra/`、`Runtime/` | 不同 Agent 工程方向的调研资料 |
| [FoodAssistant/README.md](FoodAssistant/README.md) | 美食小助手项目入口 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | GitHub 协作与变更规范 |

## 推荐学习顺序

1. 先读项目的需求、架构、安全边界和工具契约。
2. 先实现分支 1，理解一次完整的 Agent Loop。
3. 用固定评测集验证后，再实现 LangGraph 分支并对照抽象差异。
4. 最后实现 TypeScript 分支，比较语言生态，不同时引入过多新概念。
5. 每次只改变一个变量，并记录质量、延迟、成本和失败原因。

## 当前未决定事项

- 各供应商的实际模型 ID、额度和价格；这些内容应作为运行配置维护，不写死在设计中。
- 是否允许自动切换到付费模型；当前安全默认值为“不允许”。

## 许可证

本仓库采用 [MIT License](LICENSE)。
