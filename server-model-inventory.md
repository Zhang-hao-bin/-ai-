# 服务器模型检查记录

检查日期：2026-10-05（Asia/Shanghai）。目标：用户提供的四卡服务器（公开版本已省略地址与登录名）。
本次只读检查，未启动、停止或修改服务器服务；未保存登录密码。

## 本地模型文件

| 模型目录名称 | 绝对路径 | safetensors 大小 | 权重索引检查 |
| --- | --- | --- | --- |
| Qwen2.5-7B-Instruct | /srv/models/Qwen2.5-7B-Instruct | 14.19 GiB | 4 个分片均存在 |
| qwen3-vl-8b-instruct | /srv/models/qwen3-vl-8b-instruct | 16.33 GiB | 4 个分片均存在 |
| Qwen3.6-35B-A3B-FP8 | /srv/models/Qwen3.6-35B-A3B-FP8 | 34.89 GiB | 42 个分片均存在 |

模型名称来自目录，未通过实际加载验证版本、权重内容或推理效果。
35B 目录 config.json 的 model_type 为 qwen3_5_moe，architectures 为 Qwen3_5MoeForConditionalGeneration。

## GPU 与服务状态

- 4 张 NVIDIA GeForce RTX 3090，每张 24576 MiB。
- 检查时每张显存已使用约 10.2–10.6 GiB，计算进程为 另一个训练任务。
- 存在 部署目录中的 docker-compose.yml，配置 vLLM、端口 8000、tensor-parallel-size=4。
- 当前 8000 未监听，docker 列表未见 qwen-vllm 容器。
- 未发现当前用户可见的 vLLM / SGLang / Ollama 常见服务进程。
- 对当前监听的若干 HTTP 端口使用无代理 localhost 请求 /v1/models，未获得有效模型列表。
- 9080 返回 403，不能据此排除其背后存在需鉴权服务。

结论：已找到本地模型权重和部署配置，尚未确认有可直接接入项目的运行中模型 API。
后续启动需先明确 GPU 使用安排，并验证推理环境、显存与模型兼容性。

本文件是初次检查的历史记录，不代表当前运行状态；为便于公开分享，地址、用户名和路径已匿名化，表中路径为示例。后续接入与长上下文验证见 deployment-qwen.md。
