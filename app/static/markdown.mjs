import MarkdownIt from './vendor/markdown-it.mjs';

// 仅由 Markdown 解析器生成标签；原始 HTML 不执行，模型图片不发起网络请求。
const markdown = new MarkdownIt({html: false, breaks: true, linkify: false, typographer: false});
markdown.validateLink = url => /^(https?:|mailto:)/i.test(url);
markdown.renderer.rules.image = (tokens, index) => markdown.utils.escapeHtml(tokens[index].content);
const renderLink = markdown.renderer.rules.link_open
  ?? ((tokens, index, options, env, self) => self.renderToken(tokens, index, options));
markdown.renderer.rules.link_open = (tokens, index, options, env, self) => {
  tokens[index].attrSet('target', '_blank');
  tokens[index].attrSet('rel', 'noopener noreferrer');
  return renderLink(tokens, index, options, env, self);
};

export function renderAnswer(text) {
  return markdown.render(text);
}
