export const STORAGE_KEY = 'life-guide-conversations-v1';

const validSource = source => source && ['id', 'label', 'content', 'url'].every(key => typeof source[key] === 'string');
const validMessage = message => message && ['user', 'assistant'].includes(message.role)
  && typeof message.content === 'string' && Array.isArray(message.sources) && message.sources.every(validSource);
const validSession = session => session && typeof session.id === 'string' && typeof session.title === 'string'
  && typeof session.draft === 'string' && Number.isFinite(session.createdAt) && Number.isFinite(session.updatedAt)
  && Array.isArray(session.messages) && session.messages.every(validMessage);

export class ChatSessions {
  constructor(storage, {now = () => Date.now(), id = () => crypto.randomUUID()} = {}) {
    this.storage = storage;
    this.now = now;
    this.id = id;
    this.error = '';
    this.state = {version: 1, activeId: null, nextNumber: 1, sessions: []};
    this.load();
  }

  load() {
    try {
      const raw = this.storage?.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (parsed.version !== 1 || !Array.isArray(parsed.sessions) || !parsed.sessions.every(validSession)
          || new Set(parsed.sessions.map(session => session.id)).size !== parsed.sessions.length) {
        throw new Error('invalid saved sessions');
      }
      this.state = parsed;
      this.state.nextNumber = Number.isInteger(parsed.nextNumber) && parsed.nextNumber > 0
        ? parsed.nextNumber : parsed.sessions.length + 1;
      if (!this.get(parsed.activeId)) this.state.activeId = null;
      // 页面关闭会中断客户端等待，但已发送的问题必须保留。
      let recovered = false;
      for (const session of this.state.sessions) {
        if (session.pending) {
          session.pending = false;
          session.messages.push({role: 'assistant', content: '上次回答在页面关闭或刷新时中断了。问题已保留，你可以重新发送。',
            sources: [], mode: 'interrupted', createdAt: this.now()});
          recovered = true;
        }
      }
      if (recovered) this.save();
    } catch {
      this.error = '历史记录暂时无法读取。请先导出或备份浏览器数据，避免覆盖原记录。';
      this.readFailed = true;
    }
  }

  save() {
    if (this.readFailed) return false;
    try {
      if (!this.storage) throw new Error('storage unavailable');
      this.storage.setItem(STORAGE_KEY, JSON.stringify(this.state));
      this.error = '';
      return true;
    } catch {
      this.error = '浏览器未能保存记录，可能空间不足或存储被禁用。当前对话仍可继续，请先复制需要保留的内容。';
      return false;
    }
  }

  get(id) { return this.state.sessions.find(session => session.id === id); }
  get active() { return this.get(this.state.activeId); }
  list() { return [...this.state.sessions].sort((a, b) => b.updatedAt - a.updatedAt); }

  create() {
    const timestamp = this.now();
    const session = {id: this.id(), title: `新对话 ${this.state.nextNumber++}`, createdAt: timestamp,
      updatedAt: timestamp, draft: '', messages: [], pending: false, unread: false};
    this.state.sessions.push(session);
    this.state.activeId = session.id;
    this.save();
    return session;
  }

  select(id) {
    const session = this.get(id);
    if (!session) return false;
    this.state.activeId = id;
    session.unread = false;
    this.save();
    return true;
  }

  setDraft(id, draft) {
    const session = this.get(id);
    if (!session) return;
    session.draft = draft;
    this.save();
  }

  setPending(id, pending) {
    const session = this.get(id);
    if (!session) return;
    session.pending = pending;
    this.save();
  }

  append(id, message) {
    const session = this.get(id);
    if (!session) return false;
    const saved = {role: message.role, content: message.content, sources: message.sources ?? [],
      mode: message.mode ?? '', createdAt: this.now()};
    if (!validMessage(saved)) throw new Error('invalid message');
    if (message.role === 'user' && !session.messages.some(item => item.role === 'user')) {
      const title = message.content.replace(/\s+/g, ' ').trim();
      session.title = [...title].slice(0, 22).join('') + ([...title].length > 22 ? '…' : '');
    }
    session.messages.push(saved);
    session.updatedAt = this.now();
    if (message.role === 'assistant' && id !== this.state.activeId) session.unread = true;
    this.save();
    return true;
  }

  history(id) {
    return (this.get(id)?.messages ?? [])
      .filter(message => message.role === 'user' || message.mode === 'answer')
      .slice(-1000).map(message => ({role: message.role, content: message.content.slice(0, 4000)}));
  }
}
