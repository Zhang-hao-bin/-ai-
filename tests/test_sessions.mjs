import test from 'node:test';
import assert from 'node:assert/strict';
import {ChatSessions, STORAGE_KEY} from '../app/static/sessions.mjs';
import {ConversationRequests} from '../app/static/conversation.mjs';

function setup() {
  const data = new Map();
  const storage = {getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value)};
  let sequence = 0, time = 100;
  const options = {id: () => `session-${++sequence}`, now: () => ++time};
  return {storage, data, options, sessions: new ChatSessions(storage, options)};
}

test('每次新建都保存独立记录，包括空白对话', () => {
  const {sessions, storage, options} = setup();
  const first = sessions.create(), second = sessions.create();
  assert.notEqual(first.id, second.id);
  assert.equal(sessions.active.id, second.id);
  assert.equal(first.title, '新对话 1');
  assert.equal(second.title, '新对话 2');
  const restored = new ChatSessions(storage, options);
  assert.equal(restored.list().length, 2);
  assert.equal(restored.active.id, second.id);
  assert.equal(restored.select(first.id), true);
  assert.equal(restored.active.id, first.id);
});

test('刷新后恢复完整消息、引用、草稿和自动标题', () => {
  const {sessions, storage, options} = setup();
  const first = sessions.create();
  const source = {id:'S1', label:'第 4 节第 1 条', content:'完整原文', url:'https://example.test/source'};
  sessions.append(first.id, {role:'user', content:'  怎么\n 安排时间？  '});
  sessions.append(first.id, {role:'assistant', content:'回答 [S1]', sources:[source], mode:'answer'});
  sessions.setDraft(first.id, '还想问一个问题');
  const restored = new ChatSessions(storage, options);
  assert.equal(restored.active.title, '怎么 安排时间？');
  assert.equal(restored.active.draft, '还想问一个问题');
  assert.deepEqual(restored.active.messages, first.messages);
  assert.deepEqual(restored.active.messages[1].sources, [source]);
});

test('后台回答留在原会话，当前会话、草稿和上下文不被污染', () => {
  const {sessions} = setup();
  const first = sessions.create();
  sessions.append(first.id, {role:'user', content:'第一个问题'});
  sessions.setPending(first.id, true);
  const second = sessions.create();
  sessions.append(second.id, {role:'user', content:'第二个问题'});
  sessions.setDraft(second.id, '第二个草稿');
  sessions.append(first.id, {role:'assistant', content:'第一个回答', mode:'answer'});
  sessions.setPending(first.id, false);
  assert.equal(sessions.active.id, second.id);
  assert.equal(second.draft, '第二个草稿');
  assert.equal(first.unread, true);
  assert.deepEqual(sessions.history(second.id), [{role:'user', content:'第二个问题'}]);
  assert.equal(sessions.history(first.id)[1].content, '第一个回答');
  sessions.select(first.id);
  assert.equal(first.unread, false);
});

test('模型上下文限制不会截断保存的完整记录，错误消息不进入上下文', () => {
  const {sessions} = setup();
  const session = sessions.create();
  for (let i=0; i<10; i++) {
    sessions.append(session.id, {role:'user', content:String(i).repeat(5000)});
    sessions.append(session.id, {role:'assistant', content:`回答${i}`, mode:'answer'});
  }
  sessions.append(session.id, {role:'assistant', content:'连接失败', mode:'network_error'});
  const history = sessions.history(session.id);
  assert.equal(history.length, 20);
  assert.equal(history[0].content, '0'.repeat(4000));
  assert.equal(history.at(-1).content, '回答9');
  assert.equal(session.messages.length, 21);
  assert.equal(session.messages[0].content.length, 5000);
});

test('刷新中断的会话保留问题并提示重新发送，不伪造正常回答', () => {
  const {sessions, storage, options} = setup();
  const session = sessions.create();
  sessions.append(session.id, {role:'user', content:'待回答的问题'});
  sessions.setPending(session.id, true);
  const restored = new ChatSessions(storage, options);
  assert.equal(restored.active.pending, false);
  assert.equal(restored.active.messages[0].content, '待回答的问题');
  assert.equal(restored.active.messages[1].mode, 'interrupted');
  assert.equal(restored.history(session.id).length, 1);
  assert.equal(new ChatSessions(storage, options).active.messages.length, 2);
});

test('存储失败时保留当前内存记录并提供明确提示', () => {
  const storage = {getItem:()=>null, setItem:()=>{throw new Error('quota');}};
  const sessions = new ChatSessions(storage, {id:()=> 'test', now:()=>100});
  const session = sessions.create();
  sessions.append(session.id, {role:'user', content:'不能丢失的内容'});
  assert.match(sessions.error, /未能保存/);
  assert.equal(sessions.active.messages[0].content, '不能丢失的内容');
});

test('无法读取的旧存储不会被新记录自动覆盖', () => {
  const {storage, data, options} = setup();
  data.set(STORAGE_KEY, '{broken json');
  const sessions = new ChatSessions(storage, options);
  sessions.create();
  assert.match(sessions.error, /无法读取/);
  assert.equal(data.get(STORAGE_KEY), '{broken json');
});

test('多个会话的请求可以同时运行，结束一个不会取消另一个', () => {
  const first = new ConversationRequests(), second = new ConversationRequests();
  const firstRequest = first.start(), secondRequest = second.start();
  assert.equal(first.finish(firstRequest), true);
  assert.equal(secondRequest.signal.aborted, false);
  assert.equal(second.isCurrent(secondRequest), true);
  assert.equal(second.finish(secondRequest), true);
});
