// 每个会话持有独立的请求管理器，过期请求不能覆盖该会话的新请求。
export class ConversationRequests {
  constructor() {
    this.current = null;
  }

  start() {
    this.cancel();
    const request = new AbortController();
    this.current = request;
    return request;
  }

  isCurrent(request) {
    return this.current === request && !request.signal.aborted;
  }

  finish(request) {
    if (!this.isCurrent(request)) return false;
    this.current = null;
    return true;
  }

  cancel() {
    this.current?.abort();
    this.current = null;
  }
}
