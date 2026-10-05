from contextlib import asynccontextmanager
from pathlib import Path
import json
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Literal

from app.knowledge import KnowledgeIndex, load_entries
from app.service import AnswerService

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.index = KnowledgeIndex(load_entries(ROOT / "data/book"))
    app.state.service = AnswerService(ROOT, os.getenv("LLM_API_KEY", ""),
                                      os.getenv("LLM_MODEL", ""), os.getenv("LLM_BASE_URL", ""),
                                      timeout=float(os.getenv("LLM_TIMEOUT", "45")),
                                      max_tokens=int(os.getenv("LLM_MAX_TOKENS", "1500")),
                                      extra_body=json.loads(os.getenv("LLM_EXTRA_BODY", "{}")),
                                      context_window=int(os.getenv("LLM_CONTEXT_WINDOW", "8192")),
                                      tokenizer_url=os.getenv("LLM_TOKENIZER_URL", ""))
    app.state.manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
    yield


app = FastAPI(title="人生决策参考助手", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "app/static"), name="static")


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[Turn] = Field(default_factory=list, max_length=1000)


@app.get("/")
def home():
    return FileResponse(ROOT / "app/static/index.html")


@app.get("/api/status")
async def status(request: Request):
    return {"entries": len(request.app.state.index.entries),
            "model_ready": await request.app.state.service.check_connection(),
            "model_configured": request.app.state.service.enabled,
            "model_name": request.app.state.service.model,
            "context_window": request.app.state.service.context_window,
            "max_output_tokens": request.app.state.service.max_tokens,
            "knowledge": request.app.state.manifest}


@app.post("/api/chat")
async def chat(payload: ChatRequest, request: Request):
    question = payload.question.strip()
    if not question:
        raise HTTPException(422, "问题不能为空")
    index = request.app.state.index
    # 当前问题优先；短追问才补充上一条用户问题的检索上下文。
    query = question
    if len(question) < 12 and payload.history:
        previous = next((m.content for m in reversed(payload.history) if m.role == "user"), "")
        query = previous + " " + question
    entries = index.search(query)
    sources = [{"id": f"S{i}", "label": e.label, "url": e.url, "content": e.content}
               for i, e in enumerate(entries, 1)]
    service = request.app.state.service
    if not service.enabled:
        if not entries:
            return {"mode": "no_results", "answer": "当前未配置聊天模型，知识库也没有匹配条目。接入模型后即可正常聊天。", "sources": []}
        return {"mode": "retrieval", "answer": "已找到以下相关原文。当前处于原文检索模式，尚未生成 AI 建议。", "sources": sources}
    if service.base_url and not await service.check_connection():
        message = "模型暂时无法连接，先为你提供相关原文。" if sources else "模型暂时无法连接，请稍后再试。"
        return {"mode": "model_unavailable", "answer": message, "sources": sources}
    try:
        result = await service.generate(question, entries, [m.model_dump() for m in payload.history])
    except Exception as exc:
        # 不把提供商异常或请求细节传给客户端，避免泄露密钥及用户内容。
        logging.getLogger(__name__).warning("Model request failed: %s", type(exc).__name__)
        message = "本次回答生成失败，以下原文仍可查阅。" if sources else "本次回答生成失败，请稍后再试。"
        return {"mode": "model_error", "answer": message, "sources": sources}
    cited = set(result.source_ids)
    return {"mode": "answer", "answer": result.answer,
            "sources": [source for source in sources if source["id"] in cited]}
