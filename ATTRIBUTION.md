# 内容来源、改编与致谢

本项目由 Zhang-hao-bin 维护。感谢 eternity4719 及 HowToLiveBetter 项目贡献者维护《高性价比人生指南》，为本应用提供可查阅的知识正文与决策 skill。

## 知识正文

- 作品：[《高性价比人生指南》](https://github.com/eternity4719/HowToLiveBetter)。
- 作者与贡献者：[eternity4719](https://github.com/eternity4719) 及上游项目贡献者。
- 原始目录：[book/](https://github.com/eternity4719/HowToLiveBetter/tree/main/book)。
- 许可：[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)；[上游许可](https://github.com/eternity4719/HowToLiveBetter/blob/main/LICENSE)，本地副本见 [licenses/HowToLiveBetter-CC-BY-4.0.txt](licenses/HowToLiveBetter-CC-BY-4.0.txt)。

当前 `data/book/` 只有 17 个完整条目：第 3 节第 1 条、第 4 节第 1–14 条、第 8 节第 17–18 条。获取日期为 **2026-10-05**；章节文件为节选，条目正文与原始来源保留。初始节选未记录上游提交 SHA，因此不声明与某个固定提交完全一致。获取范围与后续同步身份见 [data/manifest.json](data/manifest.json)。

AI 根据正文生成的解释、比较与建议属于本应用的生成结果，不是原作者逐字撰写的内容。页面提供原文引用；制度和政策信息应结合上游最新正文及其原始来源核对。

## 决策 skill

- 来源：[skills/life-decision-guide](https://github.com/eternity4719/HowToLiveBetter/tree/main/skills/life-decision-guide)。
- 上游 `skills/` 的许可：[MIT](https://github.com/eternity4719/HowToLiveBetter/blob/main/LICENSE-CODE)。
- 版权声明：Copyright (c) 2026 eternity4719；完整版权与许可声明保留在 [licenses/HowToLiveBetter-MIT.txt](licenses/HowToLiveBetter-MIT.txt)。

[prompts/original-skill.md](prompts/original-skill.md) 保留所获取的原始 skill。[app/skill.py](app/skill.py) 将完整条目核对、成本收益比较、证据等级、适用条件和风险判断改写为应用内指令；[prompts/system.md](prompts/system.md) 加入资深、富有同情心的学者角色，并允许问候、自然交流及没有书中依据时的一般建议。原 skill 的 shell 查询流程由本应用的本地检索与知识同步工具替代，模型没有执行命令或联网检索工具。

本项目没有复制上游电子书构建工具或网页实现。

## 第三方组件

Markdown 渲染使用 [markdown-it](https://github.com/markdown-it/markdown-it) 15.0.2（MIT）；随应用分发的构建与完整许可见 [app/static/vendor/](app/static/vendor/)。其余 Python 依赖由 `pyproject.toml` 和 `uv.lock` 声明，安装时使用各自的许可证。

上述许可分别适用于所标明的上游正文、skill 和第三方组件，不把知识正文的许可混同于整个应用的代码许可。

## 项目关系

“生活书房”是独立开发的衍生应用，未由上游作者开发、审核或官方背书。致谢用于说明资源来源，不代表上游作者认可模型回答。知识正文、skill 与模型权重的权利分别归相应权利人；本仓库不分发模型权重。
