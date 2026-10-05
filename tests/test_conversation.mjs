import test from 'node:test';
import assert from 'node:assert/strict';
import {ConversationRequests} from '../app/static/conversation.mjs';

test('取消会话请求后，迟到的回答不会更新该会话', () => {
  const requests = new ConversationRequests();
  const previous = requests.start();
  requests.cancel();
  assert.equal(previous.signal.aborted, true);
  assert.equal(requests.isCurrent(previous), false);
  assert.equal(requests.finish(previous), false);
});

test('旧请求结束不会重置新请求的发送状态', () => {
  const requests = new ConversationRequests();
  const previous = requests.start();
  const current = requests.start();
  assert.equal(previous.signal.aborted, true);
  assert.equal(requests.finish(previous), false);
  assert.equal(requests.isCurrent(current), true);
  assert.equal(current.signal.aborted, false);
  assert.equal(requests.finish(current), true);
  assert.equal(requests.isCurrent(current), false);
});

test('取消后可立即发送新问题，重复取消也不会报错', () => {
  const requests = new ConversationRequests();
  requests.cancel();
  requests.start();
  requests.cancel();
  requests.cancel();
  const current = requests.start();
  assert.equal(requests.isCurrent(current), true);
  assert.equal(requests.finish(current), true);
});
