# 分支 1 NVIDIA 冒烟基线

- 日期：2026-08-27
- 分支：`branch-1-python-handwritten`
- 数据版本：`recipes-v1.0.0`
- Prompt：`food-assistant-v1`
- 供应商：NVIDIA API
- 模型：`openai/gpt-oss-20b`
- 参数：`reasoning_effort=low`、`temperature=0.2`、最多 8 个 Agent 步骤
- 付费回退：关闭

## 代表性场景

输入约束为雨天偏冷、希望吃暖和午餐，已有土豆、胡萝卜和鸡腿肉。最终运行成功推荐“胡萝卜土豆炖鸡”，食材、三步做法和 45 分钟耗时与 `get_recipe` 数据一致。

| 指标 | 结果 |
|---|---:|
| 是否完成 | 是 |
| 模型调用 | 4 |
| 工具调用 | 3 |
| 缓存命中 | 0 |
| 端到端延迟 | 10,396 ms |
| Prompt Token | 4,735 |
| Completion Token | 448 |
| Total Token | 5,183 |
| 密钥泄漏/越权/付费回退 | 0 / 0 / 0 |

## 观察

初次接入暴露了两个兼容性问题：推理预算可能挤占正文，以及托管 `gpt-oss` 偶尔把固定通道后缀拼入函数名。当前版本使用低推理强度，并只剥离已知后缀后再次执行四工具精确白名单校验；相应回归测试已加入。

这只是 1 个代表性真实冒烟场景，不等同于完整的 10 用例质量评测。当前阶段不记录费用估算，因为 NVIDIA 试用额度的实际计费信息未由运行响应提供；不得把未知费用记为零。

接口与参数依据：[NVIDIA `openai/gpt-oss-20b` Chat Completions 参考](https://docs.api.nvidia.com/nim/reference/openai-gpt-oss-20b-infer)。
