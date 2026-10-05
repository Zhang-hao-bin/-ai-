# Qwen 服务器接入

目标模型：Qwen3.6-35B-A3B-FP8。

公开文档中的服务器目录为示例；请替换为自己的绝对路径。实际服务器连接信息及密钥保存在本地私有配置中，不随公开版本上传。
模型路径：`/srv/models/Qwen3.6-35B-A3B-FP8`。
推理服务工作目录：`/srv/life-guide-llm`。

独立 vLLM 服务使用 `serve.yaml`，仅监听服务器 `127.0.0.1:18080`。
生成的 API 密钥保存在服务器 `api-key` 和本地 `.env`，文件权限为 600，未写入 Git。
SSH 登录密码未保存在项目里。

初始资源配置：四卡张量并行，每卡显存比例 0.48，文本模式，最大上下文 8192，最大并发 1，批处理 token 上限 512，关闭 CUDA graph。长上下文配置与最终检查结果见下文。
参数以服务器最终成功启动的 serve.yaml 为准；不会执行上游含 pkill 的 start.sh。

## 连接模型

在单独终端保持隧道运行：

```bash
bash scripts/connect_model.sh <服务器地址> <SSH用户名> <SSH端口>
```

首次连接应先使用普通 SSH 登录并核对主机指纹，将主机登记到 known_hosts；脚本保持严格主机校验。SSH 会提示输入登录密码，也可使用已配置的 SSH 密钥。脚本还支持 SSH_HOST、SSH_USER、SSH_PORT 环境变量。另一个终端启动助手：

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

本地应用访问 `http://127.0.0.1:18080/v1`，流量经 SSH 加密转发到服务器。
`.env` 中指定模型标识、输出上限与请求超时。Qwen 的 `enable_thinking=false` 通过服务扩展参数发送。

## 服务器维护

只管理 `/srv/life-guide-llm/server.pid` 记录的本项目进程，不停止其他用户训练或推理服务。
日志位于同目录 `server.log`；配置含 API 密钥，分享时必须隐藏密钥。
目前使用独立后台进程，尚未配置服务器重启后的自动启动。

## 验证范围

完整接入需要实际通过：健康检查、鉴权模型列表、一次 Chat Completions、助手带引用回答。
单元测试采用模拟模型，不替代真实推理验证。训练与推理共享 GPU，实际速度和可用显存随训练负载变化。

## 2026-10-05 启动检查

- 新服务进程 PID 626894，使用以上共享资源配置启动。
- 日志已确认架构解析为 Qwen3_5MoeForConditionalGeneration，已进入四卡 NCCL 初始化。
- 尚未获得健康检查成功或模型实际回答。
- 随后服务器 SSH 会话无响应，新连接在 banner exchange 超时；TCP 仍能建立。
- 已向原 SSH 会话发送停止本次进程组的指令，但尚未收到执行确认。
- 需要服务器连接恢复后先核对该进程组、日志及 GPU 状态，再继续启动验证。
- 不要直接再次启动第二套进程，也不要运行上游带 pkill 的 start.sh。

## 2026-10-05 恢复验证

15:32（Asia/Shanghai）SSH 已恢复。日志确认原服务已在 14:29 启动完成，PID 626894 存活，18080 正在监听。
服务器 /health 与鉴权 /v1/models 均返回 200，模型标识为 Qwen3.6-35B-A3B-FP8。
重新建立 SSH 隧道后，助手实际担保问答返回 mode=answer，引用 S1/S2 均通过编号校验，首次请求用时约 37.6 秒。
模型第一轮推理触发了若干 Triton JIT 编译。引用有效不等于全部语义正确；已针对担保身份混淆加强提示词。
随后通过网页再次测试“不愿意替朋友还钱是否该担保”，模型成功返回条件式回答及 S1/S2 引用，页面显示目标模型已连接。
本地 9 项测试通过，包括自建模型健康探测及断线回退；页面截图保存为 preview-qwen-connected.jpg。

## 长上下文配置

Qwen 官方模型卡标注原生窗口 262,144 token，经 YaRN 扩展可达 1,010,000 token：
https://huggingface.co/Qwen/Qwen3.6-35B-A3B-FP8/blob/main/README.md

对应不含真实密钥的模板见 `deployment/qwen-long-context.yaml`。实际配置保存在服务器 `serve.yaml`，原 8K 配置备份为 `serve.before-long-context-20261005.yaml`（含密钥，权限 600）。启动时保持：

```bash
VLLM_ALLOW_LONG_MAX_MODEL_LEN=1 vllm serve --config /srv/life-guide-llm/serve.yaml
```

不要在已有服务运行时直接启动第二个实例。只管理本项目 PID 所属进程组。

长窗口需要将显存比例提高到 0.85，四卡推理会占用绝大多数显存，不能按原来的半显存共享方式同时安排训练。YaRN 是扩展配置，不保证百万 token 中的每条信息都能被准确记住；较短文本也可能受静态缩放影响。

本地 `.env` 配置 `LLM_CONTEXT_WINDOW=1010000` 和 `LLM_TOKENIZER_URL=http://127.0.0.1:18080/tokenize`。应用最多发送最近 1000 条有效消息，按真实分词结果选择可容纳的最新历史，预留 1500 token 回答及 512 token 余量；完整记录仍在浏览器内保存。单条历史发送上限 4000 字符，输入框仍为 2000 字符。

长输入等待时间将 `.env` 的 `LLM_TIMEOUT` 设为 3600 秒；超时上限不会提升生成速度。

## 2026-10-05 长上下文验证结果

- 最终 PID 918609；vLLM 0.21.0，显存比例 0.85，YaRN factor=4。
- `/v1/models` 和 `/tokenize` 均报告 `max_model_len=1010000`；健康检查成功。
- 缓存约 10.94 GiB/卡，总容量 1,144,420 token，按百万窗口计算并发容量约 1.13x（配置仍限制单并发）。
- 每卡显存占用约 20,977 MiB，剩余约 3,148 MiB。
- 12,033 token 的真实测试输入成功生成回答（约 7 秒），正确返回开头的合成测试记号。
- 应用内真实问候成功返回；前端正常显示加粗，旧记录的 Markdown 也会重新排版。
- 未对完整百万 token 输入做压力测试，实际长输入耗时与召回准确率仍需专门评测。
