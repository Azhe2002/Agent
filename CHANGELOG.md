# Changelog

本项目使用简化的变更记录。正式版本发布后可迁移到 Keep a Changelog 规范。

## Unreleased

### Added

- 根目录项目入口、安全策略、协作规范和 AI Agent 工作守则。
- 美食小助手的需求、架构、供应商路由、安全、评测与路线图文档。
- 三个实现分支的无代码学习骨架。
- Git 密钥排除、运行产物排除和 GitHub Issue/PR 模板。
- 本地 `*_API_KEY_FILE` 密钥指针配置及对应 ADR；真实密钥无需复制进 `.env`。
- 分支 1 的 NVIDIA 客户端、手写 Agent Loop、四个只读工具、缓存、CLI 和离线测试。
- 25 道原创教学菜谱、模拟库存和 10 个共享核心评测场景。
- Claude 协作守则与分支 1 标准库实现 ADR。

### Security

- 将本地 `APIKEY/`、环境文件、私钥、凭据、日志和 trace 排除在版本控制之外。
- 明确付费模型回退默认关闭。
- 限制 NVIDIA 主机、密钥文件路径、Agent 步数、单轮工具数和重复调用；运行日志默认脱敏。
