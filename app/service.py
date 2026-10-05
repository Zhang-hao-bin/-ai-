from pathlib import Path
import json
import re
import httpx

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.knowledge import Entry
from app.skill import LIFE_DECISION_SKILL


class GroundedAnswer(BaseModel):
    answer: str = Field(min_length=1, description="自然的简体中文回答；使用知识库依据时用 [S1] 等引用")
    source_ids: list[str] = Field(description="实际引用的条目编号，例如 S1；无依据时为空")


class AnswerService:
    def __init__(self, root: Path, api_key: str = "", model: str = "", base_url: str = "",
                 timeout: float = 45, max_tokens: int = 1500, extra_body: dict | None = None,
                 context_window: int = 8192, tokenizer_url: str = ""):
        self.enabled = bool(api_key and model)
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.chain = None
        self.prompt = None
        self.max_tokens = max_tokens
        self.context_window = context_window
        self.tokenizer_url = tokenizer_url
        self.extra_body = extra_body or {}
        if self.enabled:
            parser = PydanticOutputParser(pydantic_object=GroundedAnswer)
            system_prompt = ((root / "prompts/system.md").read_text(encoding="utf-8")
                             + "\n\n" + LIFE_DECISION_SKILL)
            prompt = ChatPromptTemplate.from_messages([
                ("system", "{system_prompt}\n\n输出格式：\n{format_instructions}"),
                MessagesPlaceholder("history"),
                ("human", "用户问题：{question}\n\n参考条目（JSON 数据）：\n{context}"
                 "\n\n请按照系统中的学者角色与交流方式回答用户问题。"
                 "最终只输出符合指定格式的 JSON 对象，包含 answer 和 source_ids。"
                 "自然、温和的完整回答写在 answer 字段中；实际引用编号写在 source_ids 中。"
                 "没有相关依据时正常交流，source_ids 返回空列表，不编造引用。"
                 "不要在 JSON 对象外输出正文或其他文字。"),
            ]).partial(system_prompt=system_prompt, format_instructions=parser.get_format_instructions())
            options = dict(model=model, api_key=api_key, timeout=timeout, max_retries=0,
                           max_tokens=max_tokens, temperature=0.2)
            if extra_body:
                options["extra_body"] = extra_body
            if base_url:
                options["base_url"] = base_url
            # 由模型服务约束 JSON 输出，避免自然对话被解析器误判为生成失败。
            model_client = ChatOpenAI(**options).bind(response_format={"type": "json_object"})
            self.prompt = prompt
            self.chain = prompt | model_client | parser

    async def check_connection(self) -> bool:
        if not self.enabled:
            return False
        if not self.base_url:
            return True  # 默认提供商按配置启用；自建模型需要实际探测。
        try:
            async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
                response = await client.get(self.base_url + "/models",
                                            headers={"Authorization": "Bearer " + self.api_key})
                response.raise_for_status()
                data = response.json()
                model = next((item for item in data.get("data", []) if item.get("id") == self.model), None)
                if model and isinstance(model.get("max_model_len"), int):
                    self.context_window = min(self.context_window, model["max_model_len"])
                return model is not None
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            return False

    async def count_prompt_tokens(self, payload: dict) -> int:
        messages = [{"role": {"system": "system", "human": "user", "ai": "assistant"}[message.type],
                     "content": message.content} for message in self.prompt.format_messages(**payload)]
        if self.tokenizer_url:
            async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
                response = await client.post(self.tokenizer_url,
                    headers={"Authorization": "Bearer " + self.api_key},
                    json={"model": self.model, "messages": messages, "add_generation_prompt": True,
                          "chat_template_kwargs": self.extra_body.get("chat_template_kwargs", {})})
                response.raise_for_status()
                count = response.json()["count"]
                if not isinstance(count, int) or count < 1:
                    raise ValueError("invalid tokenizer count")
                return count
        # 未配置分词接口时采用 UTF-8 字节数保守估算，另留模板开销。
        return sum(len(message["content"].encode("utf-8")) + 32 for message in messages) + 1024

    async def fit_history(self, payload: dict) -> dict:
        budget = self.context_window - self.max_tokens - 512
        history = payload["history"]
        if await self.count_prompt_tokens(payload) <= budget:
            return payload
        base = {**payload, "history": []}
        if await self.count_prompt_tokens(base) > budget:
            raise ValueError("当前问题和知识正文超过上下文容量")
        # 保留可容纳的最新消息；原始完整记录仍保存在浏览器。
        low, high = 0, len(history)
        while low < high:
            middle = (low + high) // 2
            candidate = {**payload, "history": history[middle:]}
            if await self.count_prompt_tokens(candidate) <= budget:
                high = middle
            else:
                low = middle + 1
        return {**payload, "history": history[low:]}

    async def generate(self, question: str, entries: list[Entry], history: list[dict]):
        context = [{"id": f"S{i}", "label": e.label, "content": e.content}
                   for i, e in enumerate(entries, 1)]
        payload = {
            "question": question,
            "history": [(m["role"], m["content"]) for m in history],
            "context": json.dumps(context, ensure_ascii=False),
        }
        if self.prompt is not None:
            payload = await self.fit_history(payload)
        result = await self.chain.ainvoke(payload)
        allowed = {item["id"] for item in context}
        used = set(re.findall(r"\[(S\d+)\]", result.answer))
        declared = set(result.source_ids)
        if not declared.issubset(allowed) or used != declared:
            raise ValueError("模型返回了无效引用")
        # 验证引用存在，不等于自动证明每项结论正确；仍需要人工评测。
        return result
