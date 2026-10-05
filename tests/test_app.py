from pathlib import Path
import asyncio

from fastapi.testclient import TestClient
import pytest

from app.knowledge import KnowledgeIndex, load_entries
from app.main import app, ROOT
from app.service import AnswerService, GroundedAnswer


def test_guarantee_retrieval_preserves_full_conditions():
    index = KnowledgeIndex(load_entries(ROOT / "data/book"))
    result = index.search("朋友让我替他担保，签不签？")
    assert result[0].section == 8 and result[0].number == 18
    assert "一般保证" in result[0].content
    assert "连带责任保证" in result[0].content
    assert "- 备注：" in result[0].content


def test_time_question_and_outside_knowledge():
    index = KnowledgeIndex(load_entries(ROOT / "data/book"))
    assert any(e.section == 4 for e in index.search("怎么高性价比安排时间？"))
    assert index.search("火星探测器轨道参数") == []


def test_incomplete_entry_is_not_indexed(tmp_path):
    (tmp_path / "01-test.md").write_text("### 1. 缺了备注的条目\n- 成本：0\n- 收益：大\n- 证据等级：A\n- 来源：test", encoding="utf-8")
    assert load_entries(tmp_path) == []


def test_api_without_model(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        status = client.get("/api/status").json()
        assert not status["model_ready"] and status["entries"] >= 17
        result = client.post("/api/chat", json={"question": "替朋友担保？"}).json()
        assert result["mode"] == "retrieval" and result["sources"]
        assert client.post("/api/chat", json={"question": "火星探测器轨道参数"}).json()["mode"] == "no_results"
        assert client.post("/api/chat", json={"question": "   "}).status_code == 422
        assert client.post("/api/chat", json={"question": "a" * 2001}).status_code == 422


class FakeChain:
    def __init__(self, answer):
        self.answer = answer

    async def ainvoke(self, payload):
        self.payload = payload
        return self.answer


def test_model_citations_are_checked():
    entry = KnowledgeIndex(load_entries(ROOT / "data/book")).search("担保")[0]
    service = AnswerService(ROOT)
    service.chain = FakeChain(GroundedAnswer(answer="先看清保证方式。[S1]", source_ids=["S1"]))
    assert asyncio.run(service.generate("担保？", [entry], [])).source_ids == ["S1"]
    service.chain = FakeChain(GroundedAnswer(answer="不存在的引用。[S99]", source_ids=["S99"]))
    with pytest.raises(ValueError):
        asyncio.run(service.generate("担保？", [entry], []))


def test_general_chat_allows_no_sources_but_rejects_fabricated_citations():
    service = AnswerService(ROOT)
    service.chain = FakeChain(GroundedAnswer(answer="你好，很高兴和你聊聊。", source_ids=[]))
    assert asyncio.run(service.generate("你好", [], [])).source_ids == []
    # 检索到的条目不适用于当前话题时，也不能被强行引用。
    entry = KnowledgeIndex(load_entries(ROOT / "data/book")).search("担保")[0]
    assert asyncio.run(service.generate("你好", [entry], [])).source_ids == []
    service.chain = FakeChain(GroundedAnswer(answer="书中说过。[S1]", source_ids=["S1"]))
    with pytest.raises(ValueError):
        asyncio.run(service.generate("你好", [], []))


def test_greeting_without_knowledge_reaches_model_and_keeps_history(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.setenv("LLM_BASE_URL", "")
    with TestClient(app) as client:
        app.state.service.enabled = True
        chain = FakeChain(GroundedAnswer(answer="你好，你想聊些什么？", source_ids=[]))
        app.state.service.chain = chain
        result = client.post("/api/chat", json={"question": "你好"}).json()
        assert result["mode"] == "answer" and result["sources"] == []
        assert "你好" in result["answer"]
        assert chain.payload["context"] == "[]"
        history = [{"role": "user", "content": "你好"},
                   {"role": "assistant", "content": result["answer"]}]
        result = client.post("/api/chat", json={"question": "火星探测器轨道参数", "history": history}).json()
        assert result["mode"] == "answer" and result["sources"] == []
        assert chain.payload["history"] == [(m["role"], m["content"]) for m in history]


def test_model_failure_returns_sources(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("LLM_MODEL", "")
    monkeypatch.setenv("LLM_BASE_URL", "")
    with TestClient(app) as client:
        app.state.service.enabled = True
        app.state.service.chain = FakeChain(GroundedAnswer(answer="无效引用。[S99]", source_ids=["S99"]))
        result = client.post("/api/chat", json={"question": "担保签不签"}).json()
        assert result["mode"] == "model_error"
        assert result["sources"]


def test_custom_model_requires_matching_model_list(monkeypatch):
    import httpx
    async def get_model(client, url, **kwargs):
        return httpx.Response(200, json={"data": [{"id": "Qwen3.6-35B-A3B-FP8"}]},
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.AsyncClient, "get", get_model)
    service = AnswerService(ROOT, "test-key", "Qwen3.6-35B-A3B-FP8", "http://127.0.0.1:18080/v1",
                            extra_body={"chat_template_kwargs": {"enable_thinking": False}})
    assert asyncio.run(service.check_connection())
    service.model = "missing-model"
    assert not asyncio.run(service.check_connection())


def test_disconnected_model_falls_back_to_original(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "Qwen3.6-35B-A3B-FP8")
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:18080/v1")
    async def disconnected(service):
        return False
    monkeypatch.setattr(AnswerService, "check_connection", disconnected)
    with TestClient(app) as client:
        status = client.get("/api/status").json()
        assert status["model_configured"] and not status["model_ready"]
        result = client.post("/api/chat", json={"question": "担保签不签"}).json()
        assert result["mode"] == "model_unavailable" and result["sources"]
        greeting = client.post("/api/chat", json={"question": "你好"}).json()
        assert greeting["mode"] == "model_unavailable" and greeting["sources"] == []
        assert "原文" not in greeting["answer"]
