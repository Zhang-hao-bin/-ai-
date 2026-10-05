import test from 'node:test';
import assert from 'node:assert/strict';
import {renderAnswer} from '../app/static/markdown.mjs';

test('模型的粗体、星号列表和标题转为正常排版', () => {
  const html = renderAnswer('## 小小的开始\n\n**设定微小的“锚点”**：先做一步。\n\n* 写一句话\n* 整理桌面');
  assert.match(html, /<h2>小小的开始<\/h2>/);
  assert.match(html, /<strong>设定微小的“锚点”<\/strong>/);
  assert.match(html, /<ul>\n<li>写一句话<\/li>\n<li>整理桌面<\/li>/);
  assert.equal(html.includes('**'), false);
});

test('HTML 和脚本内容只显示为文字', () => {
  const html = renderAnswer('<script>alert(1)</script>\n<img src=x onerror=alert(1)>');
  assert.equal(html.includes('<script>'), false);
  assert.equal(html.includes('<img'), false);
  assert.match(html, /&lt;script&gt;/);
});

test('危险链接、相对链接和远程图片不能进入回答 DOM', () => {
  const html = renderAnswer('[脚本](javascript:alert(1)) [数据](data:text/html,x) [相对](/api/chat) ![图片说明](https://example.test/tracking.png)');
  assert.equal(html.includes('href='), false);
  assert.equal(html.includes('<img'), false);
  assert.match(html, /图片说明/);
});

test('正常 HTTPS 链接保留并使用安全的新标签页', () => {
  const html = renderAnswer('[来源](https://example.test/?q=a&b=c)');
  assert.match(html, /href="https:\/\/example.test\/\?q=a&amp;b=c"/);
  assert.match(html, /target="_blank"/);
  assert.match(html, /rel="noopener noreferrer"/);
});

test('代码中的星号和非 Markdown 星号保留原意', () => {
  const html = renderAnswer('`**literal**`\n\n```txt\na * b\n```\n\n2 * 3 = 6');
  assert.match(html, /<code>\*\*literal\*\*<\/code>/);
  assert.match(html, /a \* b/);
  assert.match(html, /2 \* 3 = 6/);
});
