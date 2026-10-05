import asyncio
import httpx
import pytest
from app.main import ROOT
from app.service import AnswerService


def test_long_history_is_not_limited_to_eight_messages():
    service = AnswerService(ROOT, context_window=1010000)
    async def count(payload):
        return 200 + len(payload['history']) * 100
    service.count_prompt_tokens = count
    payload = {'question':'继续', 'context':'[]', 'history':[('user',str(i)) for i in range(24)]}
    fitted = asyncio.run(service.fit_history(payload))
    assert fitted == payload
    assert len(fitted['history']) == 24


def test_budget_reserves_answer_and_keeps_latest_history():
    service = AnswerService(ROOT, context_window=2000, max_tokens=100)
    async def count(payload):
        return 200 + len(payload['history']) * 100
    service.count_prompt_tokens = count
    payload = {'question':'继续', 'context':'[]', 'history':[('user',str(i)) for i in range(15)]}
    fitted = asyncio.run(service.fit_history(payload))
    assert fitted['history'] == payload['history'][-11:]
    assert len(payload['history']) == 15
    assert asyncio.run(count(fitted)) + service.max_tokens + 512 <= service.context_window


def test_current_question_is_never_silently_cut():
    service = AnswerService(ROOT, context_window=2000, max_tokens=100)
    async def count(payload):
        return 1500
    service.count_prompt_tokens = count
    with pytest.raises(ValueError, match='超过上下文容量'):
        asyncio.run(service.fit_history({'question':'长问题', 'context':'[]', 'history':[]}))


def test_tokenizer_receives_complete_chat_template_and_disables_thinking(monkeypatch):
    async def post(client, url, **kwargs):
        assert url == 'http://localhost:18080/tokenize'
        assert kwargs['json']['add_generation_prompt'] is True
        assert kwargs['json']['chat_template_kwargs'] == {'enable_thinking':False}
        messages = kwargs['json']['messages']
        assert messages[0]['role'] == 'system'
        assert messages[1] == {'role':'user','content':'前一个问题'}
        assert '当前问题' in messages[2]['content']
        return httpx.Response(200, json={'count':123}, request=httpx.Request('POST',url))
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    service = AnswerService(ROOT, 'test-key', 'test-model', tokenizer_url='http://localhost:18080/tokenize',
                            extra_body={'chat_template_kwargs':{'enable_thinking':False}})
    payload = {'question':'当前问题','context':'[]','history':[('user','前一个问题')]}
    assert asyncio.run(service.count_prompt_tokens(payload)) == 123


def test_actual_server_capacity_caps_configured_window(monkeypatch):
    async def get(client, url, **kwargs):
        return httpx.Response(200, json={'data':[{'id':'test-model','max_model_len':262144}]},
                              request=httpx.Request('GET',url))
    monkeypatch.setattr(httpx.AsyncClient,'get',get)
    service = AnswerService(ROOT,'test-key','test-model','http://localhost/v1',context_window=1010000)
    assert asyncio.run(service.check_connection())
    assert service.context_window == 262144


def test_api_accepts_more_than_eight_turns_without_mixing_history(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.service import GroundedAnswer
    monkeypatch.setenv('LLM_API_KEY','')
    monkeypatch.setenv('LLM_MODEL','')
    monkeypatch.setenv('LLM_BASE_URL','')
    class Chain:
        async def ainvoke(self, payload):
            assert len(payload['history']) == 12
            assert payload['history'][0] == ('user','第0个问题')
            return GroundedAnswer(answer='仍然记得前面的讨论。',source_ids=[])
    with TestClient(app) as client:
        app.state.service.enabled = True
        app.state.service.chain = Chain()
        history = [{'role':'user','content':f'第{i}个问题'} for i in range(12)]
        result = client.post('/api/chat',json={'question':'继续讨论','history':history})
        assert result.status_code == 200
        assert result.json()['mode'] == 'answer'
