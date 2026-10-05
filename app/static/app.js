import {ConversationRequests} from './conversation.mjs';
import {ChatSessions} from './sessions.mjs';
import {renderAnswer} from './markdown.mjs';

const form = document.querySelector('#chat-form');
const input = document.querySelector('#question');
const messages = document.querySelector('#messages');
const send = document.querySelector('#send');
const sendLabel = document.querySelector('#send-label');
const clear = document.querySelector('#clear');
const newChat = document.querySelector('#new-chat');
const welcome = document.querySelector('#welcome');
const suggestions = document.querySelector('#suggestions');
const conversationHeading = document.querySelector('#conversation-heading');
const workspace = document.querySelector('#workspace');
const conversationNotice = document.querySelector('#conversation-notice');
const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
let storage;
try { storage = window.localStorage; } catch { storage = null; }
const sessions = new ChatSessions(storage);
const requests = new Map();
const sessionList = document.querySelector('#sessions-list');
const library = document.querySelector('#session-library');
const mobileLibrary = window.matchMedia('(max-width: 760px)');
let busy = false;
if (mobileLibrary.matches) library.open = false;
mobileLibrary.addEventListener('change', event => { library.open = !event.matches; });

function setConversationState(active) {
  workspace.classList.toggle('is-chatting', active);
  welcome.hidden = active;
  suggestions.hidden = active;
  conversationHeading.hidden = !active;
}

function addMessage(role, text, sources = []) {
  const article = document.createElement('article');
  article.className = `message ${role}`;
  const tag = document.createElement('div');
  tag.className = 'message-head';
  if (role === 'assistant') {
    const mark = document.createElement('span');
    mark.className = 'assistant-mark';
    mark.append(document.querySelector('#assistant-mark').content.cloneNode(true));
    tag.append(mark);
  }
  const name = document.createElement('span');
  name.textContent = role === 'user' ? '你' : '书房助手';
  tag.append(name);
  const body = document.createElement('div');
  body.className = 'text';
  if (role === 'assistant') {
    body.classList.add('markdown');
    body.innerHTML = renderAnswer(text);
  } else {
    body.textContent = text;
  }
  article.append(tag, body);
  if (sources.length) {
    const list = document.createElement('div'); list.className = 'sources';
    const heading = document.createElement('p');
    heading.className = 'sources-heading'; heading.textContent = `参考的书页 · ${sources.length} 条依据`;
    list.append(heading);
    for (const source of sources) {
      const detail = document.createElement('details');
      const summary = document.createElement('summary');
      const number = document.createElement('span'); number.className = 'source-number'; number.textContent = source.id;
      const label = document.createElement('span'); label.textContent = source.label;
      summary.append(number, label);
      const original = document.createElement('div'); original.className = 'original';
      original.textContent = source.content.replace(/^### .+\n/, '').replace(/^<!--.*-->\s*$/gm, '').trim();
      detail.append(summary, original);
      // 参考正文按文本渲染，原文外链仅接受本项目的 GitHub 来源。
      if (source.url.startsWith('https://github.com/eternity4719/HowToLiveBetter/blob/main/book/')) {
        const link = document.createElement('a'); link.className = 'source-link'; link.textContent = '翻阅完整原文 ↗';
        link.href = source.url; link.target = '_blank'; link.rel = 'noopener noreferrer';
        detail.append(link);
      }
      list.append(detail);
    }
    article.append(list);
  }
  messages.append(article);
  return article;
}

function scrollToMessage(article) {
  article.scrollIntoView({behavior: reducedMotion.matches ? 'instant' : 'smooth', block: 'nearest'});
}

function setBusy(value) {
  busy = value; send.disabled = value;
  sendLabel.textContent = value ? '思考中' : '发送';
  form.setAttribute('aria-busy', String(value));
}

function renderSidebar() {
  sessionList.replaceChildren();
  const list = sessions.list();
  document.querySelector('#session-count').textContent = String(list.length);
  if (!list.length) {
    const empty = document.createElement('p'); empty.className = 'sessions-empty';
    empty.textContent = '每次新的对话，都会留在这里。'; sessionList.append(empty);
  }
  for (const session of list) {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'session-item';
    button.setAttribute('aria-pressed', String(session.id === sessions.state.activeId));
    const title = document.createElement('span'); title.className = 'session-title'; title.textContent = session.title;
    const meta = document.createElement('span'); meta.className = 'session-meta';
    const date = new Intl.DateTimeFormat('zh-CN', {month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit'}).format(session.updatedAt);
    meta.textContent = `${session.messages.length} 条消息 · ${date}`;
    button.append(title, meta);
    if (session.pending || session.unread) {
      const badge = document.createElement('span'); badge.className = 'session-badge';
      badge.textContent = session.pending ? '正在回答' : '有新回答'; button.append(badge);
    }
    button.addEventListener('click', () => {
      sessions.select(session.id); renderCurrent();
      if (mobileLibrary.matches) library.open = false;
      const last = messages.lastElementChild;
      if (last) scrollToMessage(last);
      else window.scrollTo({top: 0, behavior: reducedMotion.matches ? 'instant' : 'smooth'});
      input.focus({preventScroll: true});
    });
    sessionList.append(button);
  }
  renderStorageWarning();
}

function renderStorageWarning() {
  const warning = document.querySelector('#storage-warning');
  warning.textContent = sessions.error; warning.hidden = !sessions.error;
}

function addThinking() {
  const thinking = addMessage('assistant', '正在梳理思路');
  thinking.classList.add('thinking');
  const dots = document.createElement('span'); dots.className = 'thinking-dots'; dots.setAttribute('aria-hidden', 'true');
  for (let i = 0; i < 3; i++) dots.append(document.createElement('span'));
  thinking.querySelector('.text p').append(dots);
}

function renderCurrent() {
  messages.replaceChildren();
  const session = sessions.active;
  setConversationState(Boolean(session));
  setBusy(Boolean(session?.pending));
  input.value = session?.draft ?? ''; input.style.height = '';
  conversationNotice.hidden = !session || session.messages.length > 0;
  conversationNotice.textContent = '这是独立的新对话。记录会自动保存在当前浏览器。';
  document.querySelector('#conversation-title').textContent = session?.title ?? '每个选择，都值得好好想一想。';
  for (const message of session?.messages ?? []) addMessage(message.role, message.content, message.sources);
  if (session?.pending) addThinking();
  renderSidebar();
}

function createConversation() {
  sessions.create(); renderCurrent();
  document.querySelector('#about').open = false;
  if (mobileLibrary.matches) library.open = false;
  input.focus({preventScroll: true});
  window.scrollTo({top: 0, behavior: reducedMotion.matches ? 'instant' : 'smooth'});
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question || busy) return;
  const session = sessions.active ?? sessions.create();
  const id = session.id;
  const history = sessions.history(id);
  if (!requests.has(id)) requests.set(id, new ConversationRequests());
  const manager = requests.get(id);
  const request = manager.start();
  sessions.setDraft(id, '');
  sessions.append(id, {role: 'user', content: question});
  sessions.setPending(id, true);
  renderCurrent();
  document.querySelector('#about').open = false;
  scrollToMessage(messages.lastElementChild);
  try {
    const response = await fetch('/api/chat', {method: 'POST', signal: request.signal, headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({question, history})});
    if (!manager.isCurrent(request)) return;
    if (!response.ok) throw new Error('request failed');
    const data = await response.json();
    if (!manager.isCurrent(request)) return;
    sessions.append(id, {role: 'assistant', content: data.answer, sources: data.sources, mode: data.mode});
  } catch {
    if (!manager.isCurrent(request)) return;
    sessions.append(id, {role: 'assistant', content: '这次没能收到回答。问题已保留，可以稍后重新发送。', mode: 'network_error'});
    if (!sessions.get(id).draft) sessions.setDraft(id, question);
  } finally {
    if (manager.finish(request)) {
      sessions.setPending(id, false);
      if (sessions.state.activeId === id) {
        renderCurrent(); scrollToMessage(messages.lastElementChild); input.focus({preventScroll: true});
      } else {
        renderSidebar();
      }
    }
  }
});

input.addEventListener('input', () => {
  if (sessions.active) sessions.setDraft(sessions.active.id, input.value);
  renderStorageWarning();
  input.style.height = 'auto';
  input.style.height = `${Math.min(input.scrollHeight, 200)}px`;
});
input.addEventListener('keydown', event => {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); form.requestSubmit(); }
});
document.querySelectorAll('[data-question]').forEach(button => button.addEventListener('click', () => {
  input.value = button.dataset.question; input.dispatchEvent(new Event('input')); input.focus();
}));
clear.addEventListener('click', () => {
  if (sessions.active) sessions.setDraft(sessions.active.id, '');
  renderStorageWarning();
  input.value = ''; input.style.height = ''; input.focus();
});
newChat.addEventListener('click', createConversation);
renderCurrent();

fetch('/api/status').then(response => {
  if (!response.ok) throw new Error('status failed');
  return response.json();
}).then(data => {
  const mode = data.model_ready ? `AI 回答 · ${data.model_name}` : (data.model_configured ? '模型暂未连通' : '原文检索模式');
  document.querySelector('#status').textContent = `${mode} · ${data.entries} 条知识${data.model_ready ? ` · 上下文 ${data.context_window.toLocaleString()} token` : ''}`;
  document.querySelector('#scope').textContent = `${data.knowledge.description}。知识获取日期：${data.knowledge.fetched_on}`;
  const connection = document.querySelector('#connection');
  connection.textContent = data.model_ready ? '书房已就绪' : (data.model_configured ? '模型暂未连通' : '原文检索模式');
  connection.classList.toggle('ready', data.model_ready);
  connection.classList.toggle('unavailable', data.model_configured && !data.model_ready);
}).catch(() => {
  document.querySelector('#status').textContent = '服务暂不可用';
  const connection = document.querySelector('#connection');
  connection.textContent = '服务暂不可用'; connection.classList.add('unavailable');
});
