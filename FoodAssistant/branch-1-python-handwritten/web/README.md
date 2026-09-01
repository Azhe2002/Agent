# Branch 1 Web 快速测试台

这个目录提供一个仅监听本机的单页测试界面。它通过很薄的 HTTP 适配层复用上一级目录中的 `HandwrittenAgent`、模型客户端和四个只读工具，不复制或改变 Agent 行为。

## 启动

先按分支 README 配置 `FoodAssistant/.env`，然后在仓库根目录执行：

```powershell
& 'D:\Program Files\Python312\python.exe' FoodAssistant\branch-1-python-handwritten\web\server.py
```

浏览器打开 `http://127.0.0.1:8000`。如端口已被占用，可增加 `--port 8080`。

## 边界

- 服务固定监听 `127.0.0.1`，不提供局域网或公网访问；
- 每次提交都是独立的单轮 Agent 运行，不保存输入、回答或会话；
- “开始推荐”左侧可以在 DeepSeek、MiMo、Kimi、NVIDIA 之间显式切换，实际供应商和模型会显示在响应结果中；
- 四个选项分别读取 `DEEPSEEK_*`、`MIMO_*`、`KIMI_*`、`NVIDIA_*` 本地配置，未配置的选项会在页面中禁用；
- 请求最多 2000 个字符，同时最多运行两个测试；
- 页面只显示最终回答和脱敏摘要，不返回模型推理内容、完整载荷或凭据；
- 这是开发测试入口，不包含账号、持久化、生产部署或流式输出。

Web 白名单固定使用 DeepSeek V4 Flash、MiMo V2.5、Kimi K2.6 和 NVIDIA GPT-OSS 20B，避免陈旧或任意模型 ID 从浏览器进入请求；命令行仍可使用各供应商的 `*_MODEL` 配置。切换是逐次请求的显式选择，不会在请求失败时自动改用另一家供应商。
