# 分支 1：Python 手写 Agent Loop

## 学习目标

直接观察“模型推理 → 工具请求 → 参数校验 → 工具执行 → 观察结果 → 再次推理”的完整循环，不依赖 Agent 编排框架隐藏细节。

## 已实现范围

- NVIDIA、DeepSeek、MiMo、Kimi 的安全配置与 OpenAI 兼容 HTTP 客户端；
- 四个共享只读工具、统一参数校验、结构化错误与调用缓存；
- 显式 Agent Loop、最多 8 步、重复调用保护和有界降级回答；
- 命令行入口、本地 Web 快速测试台、脱敏事件日志、Token 与耗时摘要；
- 25 道菜谱、模拟库存、共享评测用例和离线单元测试。

## 文件导览

第一次阅读代码时，可配合 [分支 1 代码学习指南](KNOWLEDGE.md) 按执行顺序理解各模块。

| 文件 | 作用 |
|---|---|
| `main.py` | 命令行入口和安全错误出口 |
| `web/` | 本地单页测试界面与标准库 HTTP 适配层 |
| `agent.py` | 手写“模型 → 工具 → 观察 → 模型”循环 |
| `tools.py` | 数据加载、检索、四个工具与缓存 |
| `model_client.py` | 四家供应商的 OpenAI 兼容 HTTP 请求和响应解析 |
| `config.py` | `.env`、系统变量和密钥文件指针加载 |
| `tests/` | 不联网、不读取真实密钥的单元测试 |

## 本地配置

1. 复制 `../.env.example` 为本地 `../.env`。该文件已被 Git 忽略。
2. 命令行默认使用 NVIDIA，推荐设置 `NVIDIA_API_KEY_FILE`；要在 Web 测试其他供应商，再配置对应的 `DEEPSEEK_*`、`MIMO_*` 或 `KIMI_*`。密钥文件必须使用 `APIKEY/` 中各供应商的白名单文件，不要把密钥复制进配置、命令、聊天或日志。
3. 命令行默认保持 `MODEL_PROVIDER=nvidia`；Web 测试页由用户逐次显式选择供应商。始终保持 `PAID_FALLBACK_ENABLED=false`，请求失败时不会自动切换供应商。

`AGENT_REASONING_EFFORT` 默认为 `low`。这个任务的工具选择很简单，低推理强度可减少推理 Token 和延迟，并给最终中文回答留出输出空间。

配置加载器只允许四家供应商各自的官方 HTTPS 主机和指定密钥文件，且不会在对象表示、日志或错误中输出密钥。

## 运行

在仓库根目录执行：

```powershell
& 'D:\Program Files\Python312\python.exe' FoodAssistant\branch-1-python-handwritten\main.py "今天下雨有点冷，家里有土豆、胡萝卜和鸡腿肉。"
```

如需关闭过程事件，增加 `--quiet`。事件日志只含步骤、耗时、工具名、参数字段名、缓存和状态，不含用户参数值或模型原始载荷。

## Web 快速测试

完成相同的本地配置后，在仓库根目录启动只监听本机的测试页：

```powershell
& 'D:\Program Files\Python312\python.exe' FoodAssistant\branch-1-python-handwritten\web\server.py
```

然后打开 `http://127.0.0.1:8000`。页面复用同一个 Agent Loop，每次提交都是独立单轮运行；可在提交按钮左侧显式切换 DeepSeek、MiMo、Kimi 或 NVIDIA，并在结果中核对实际供应商与模型。页面只展示最终回答和脱敏摘要；详细边界见 [web/README.md](web/README.md)。

| 页面选项 | 固定 Web 模型 |
|---|---|
| DeepSeek · V4 Flash | `deepseek-v4-flash` |
| MiMo · V2.5 | `mimo-v2.5` |
| Kimi · K2.6 | `kimi-k2.6` |
| NVIDIA · GPT-OSS 20B | `openai/gpt-oss-20b` |

页面启动时会读取公开的配置状态并禁用未配置项。模型 ID 由服务端白名单固定，浏览器不能提交任意模型；任一请求失败时只显示该供应商的错误，不进行自动回退。

## 离线测试

```powershell
& 'D:\Program Files\Python312\python.exe' -m unittest discover -s FoodAssistant\branch-1-python-handwritten\tests -v
```

测试不联网，也不会读取 `APIKEY/` 或本地 `.env`。

## 当前边界

- 天气和库存都是只读 Mock，检索使用字符 n-gram，不代表生产级搜索质量；
- 命令行与本地 Web 测试页都只支持单轮任务，不保存会话记忆；
- 初版目标是看清协议和保证边界，不进行框架化或性能优化；
- 工具契约以 [共享工具契约](../shared/contracts/tools.md) 为准，本分支不得自行改变语义。
- NVIDIA 托管的 `gpt-oss` 偶尔会把已知内部通道后缀拼入函数名；循环只移除该固定后缀，之后仍按四个工具的精确白名单校验。

## 完成条件

通过核心评测且无密钥泄漏、越权工具、无限循环和静默付费回退，再进入 LangGraph 分支。当前离线主路径已通过，真实模型稳定性仍需记录基线。
