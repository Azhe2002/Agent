# Agent 知识体系总大纲

> 由 9 篇企业 Agent 岗位 JD 的知识点汇总整理，作为学习索引，可继续补充。

## 资料来源

| 文件 | 岗位 | 主题侧重点 |
|---|---|---|
| [Agent/YiLiang.md](Agent/YiLiang.md) | Agent 开发工程师 | 应用层：RAG、上下文工程、评测体系 |
| [Runtime/Tongyuan.md](Runtime/Tongyuan.md) | Runtime · 图执行与任务编排 | 运行时底层：图执行、DAG 调度、增量计算 |
| [Harness/Huaran.md](Harness/Huaran.md) | Agent Harness 工程师 | 运行控制层：长任务、沙箱、权限、可观测性 |
| [Agent/Xiaomi.md](Agent/Xiaomi.md) | AI Agent 研发工程师（材料智能体） | 企业部署、版本治理、权限与合规 |
| [Agent/Huawei.md](Agent/Huawei.md) | AI 技术应用 / AI Agent 开发 | 训练侧：预训练/后训练、RL、数据管线 |
| [Agent/AliTaotian.md](Agent/AliTaotian.md) | 淘天 Agent | 商业落地、Agent 框架、集成协议 |
| [Agent/Kunqi.md](Agent/Kunqi.md) | AI Agent 研发实习生 | 全链路开发、数据飞轮、前端技术栈 |
| [Harness/Shendu.md](Harness/Shendu.md) | Agent Harness | 评测与数据闭环、失败归因、流量回放 |
| [Infra/Tashi.md](Infra/Tashi.md) | AI Infra 工程师 | 平台工程：会话/状态/权限/记忆等平台模块 |

---

## 一、Agent 基础概念

- **Agent（智能体）**：能感知环境、自主规划决策、调用工具执行任务的智能系统。
- **Agent Loop**：核心循环——LLM 推理 → 工具调用 → 观察结果 → 再次推理，直到任务完成。
- **Agentic Workflow**：由 Agent 驱动的工作流编排，强调鲁棒性。
- **AI-native（AI 原生）**：产品/研发流程从底层围绕 AI 设计，而非事后接入。
- **Human-in-the-loop（人在回路）**：关键节点由人类确认/接管，保证可控与可信。
- **可解释性**：Agent 的决策与执行过程可被理解、追溯与审计。

## 二、Agent 核心能力

- **任务规划（Planning）**：把复杂目标分解为可执行的子任务序列。
- **工具调用（Tool Use / Function Calling）**：模型按结构化方式请求调用外部函数/工具。
- **上下文工程（Context Engineering）**：构造、压缩、管理喂给模型的有效上下文。
- **记忆机制**：短期记忆（会话内）+ 长期记忆（跨会话持久化）。
- **模型输出解析（Output Parsing）**：把非结构化输出解析为结构化动作。
- **自主决策（Autonomous Decision-making）**：不依赖人逐步指示，独立规划决策。
- **多智能体协作**：多个 Agent 分工完成复杂任务，涉及任务分解、协作调度与结果汇总。
- **代码生成**：面向编码任务的代码产出能力。

## 三、RAG 技术体系

- **文档解析**：从 PDF、Word、HTML 中提取文本、表格、图片。
- **文本切分（Chunking）**：把长文本切成适合嵌入与检索的片段。
- **Embedding（向量化）**：把文本转换为语义向量。
- **向量检索**：基于向量相似度（如余弦相似度）召回相关片段。
- **混合检索（Hybrid Retrieval）**：关键词（BM25）与向量检索结合，兼顾精确与语义匹配。
- **重排序（Re-ranking）**：对召回结果用更强模型二次排序，提升 Top-K 质量。
- **知识引用**：回答中标注来源，可溯源、降低幻觉。
- **幻觉（Hallucination）**：模型生成与事实不符的内容，需通过检索、引用、约束等手段抑制。

## 四、Agent Runtime（运行时底层）

- **Agent Runtime**：Agent 的运行引擎/框架，负责调度、状态管理与资源控制。
- **图执行引擎**：把复杂 Agent 任务抽象为带依赖关系的执行图（节点=任务，边=依赖）。
- **DAG / 拓扑排序**：任务依赖的表达形式与排序方法，保证前驱任务先执行。
- **节点调度 / 依赖解析**：决定节点何时运行；解析数据依赖与控制依赖。
- **并行执行 / 关键路径优化**：识别无依赖节点并发执行；优化决定总时长的任务链。
- **状态管理**：跟踪节点执行状态（就绪/运行/成功/失败）。
- **增量计算**：状态缓存、结果复用、失败恢复、增量重执行——局部变化时不整链重跑。
- **执行成本优化**：减少不必要的 LLM 调用与上下文重复传递；确定性任务下沉到 Runtime。

## 五、Agent Harness（运行控制层）

- **Agent Harness**：模型与真实世界之间的"运行控制层"，让 Agent 长时间、稳定、安全、可恢复地执行任务。
- **长任务运行能力**：异步执行、断点恢复（Checkpoint/Resume）、容错重试、终止机制、用户接管。
- **工具与运行环境**：MCP、Skills、浏览器、终端、本地文件、代码仓库。
- **沙箱隔离（Sandboxing）**：在受限环境中执行代码/工具，防止危害宿主机。
- **权限控制 / 安全边界**：最小权限原则、操作授权。
- **可观测性（Observability）**：日志、trace、指标三位一体，支撑线上诊断。

## 六、AI Infra（平台工程）

- **平台核心模块**：会话管理、上下文管理、任务状态管理、记忆机制、权限控制、异常恢复。
- **部署能力**：容器化（Docker）、K8s、CI/CD、负载均衡、高可用、灰度发布、故障恢复、环境可复现。
- **治理能力**：版本化治理（知识/Skill/Prompt/配置/依赖）、自动同步、冲突保护、变更审计、发布回滚。
- **合规能力**：敏感数据处理、模型策略路由、最小权限、工具读写控制、操作审计。

## 七、Agent 评测与数据闭环

- **Benchmark / Evaluation Pipeline**：标准评测任务集与评测流水线。
- **能力维度**：理解、规划、工具调用、执行、协作、恢复。
- **失败归因（Failure Attribution）**：从失败样本定位根因（模型/上下文/工具/状态/评测/基础设施）。
- **流量回放（Traffic Replay）**：把线上真实流量回放到系统进行回归验证。
- **Agent Eval / LLM Evaluation**：面向 Agent 与大模型的自动化评测。
- **核心指标**：任务完成率、工具调用准确率、响应质量、稳定性、可恢复性、延迟、成本、用户信任。
- **数据闭环（Data Loop）**：线上失败样本、评测结果、用户行为、运行日志 → 反哺模型/Prompt/工具链/执行策略优化。
- **数据飞轮（Data Flywheel）**：使用数据 → 反哺模型 → 模型提升产品 → 产生更多数据，自增强循环。
- **自我进化（Self-improvement）**：Agent 基于闭环数据持续改进能力。

## 八、模型与训练

- **预训练 / 后训练（Pre-training / Post-training）**：预训练学通用能力，后训练（SFT/RL）适配任务。
- **模型微调（Fine-tuning）**：用领域数据适配具体业务场景。
- **强化学习（RL）与 Agent**：环境反馈驱动的策略优化，提升决策的泛化性与鲁棒性。
- **Prompt 设计**：设计高效提示词引导模型行为。
- **结构化输出（Structured Output）**：约束输出为 JSON 等固定格式。
- **多轮对话**：带历史上下文的连续对话。
- **训练数据生产管线**：复杂任务规划、Repo 级长程轨迹交互、多步工具编排等高价值数据。
- **主流大模型**：OpenAI（GPT）、Claude（Anthropic）、Gemini（Google）、DeepSeek、GLM（智谱）。

## 九、框架、协议与工具

- **Agent / LLM 框架**：LangChain、LlamaIndex、AutoGen。
- **集成协议**：OpenAPI（HTTP API 规范）、RPC（远程过程调用）、MCP（模型上下文协议）。
- **Workflow / 分布式执行系统**：Airflow、Prefect、Dagster、Temporal、Ray、Dask。
- **AI Coding 工具**：Claude Code、Codex、Cursor、OpenCode，及其能力边界与失败模式。
- **深度学习框架**：PyTorch、TensorFlow；计算图与自动微分机制（PyTorch/JAX）。

## 十、工程素养与生产环境

- **生产环境问题**：并发、超时、重试、降级、幂等、监控、日志追踪。
- **测试体系**：单元测试、集成测试、端到端（E2E）接口验证、自动化测试。
- **性能优化**：响应时延（Latency）、Token 消耗、profiling、Prompt Cache、模型路由、并发/异步执行。
- **关键技术栈**：前端（React/TypeScript/Next.js）、后端（Python(FastAPI/Flask)/Go）、Linux/Docker/CI/CD。
- **人才素质**：独立判断、跨边界协作、对 AI 能力边界有一手判断、Builder 思维、闭环意识、Self-debugging。
