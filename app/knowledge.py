"""按完整条目读取 Markdown，使用中文二元词组 BM25 检索。"""
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import math
import re
from urllib.parse import quote

REPO_URL = "https://github.com/eternity4719/HowToLiveBetter"


def tokens(text: str) -> list[str]:
    result = re.findall(r"[a-z0-9]+", text.lower())
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(run) == 1:
            continue
        result.extend(run[i:i + 2] for i in range(len(run) - 1))
    return result


@dataclass(frozen=True)
class Entry:
    section: int
    number: int
    title: str
    content: str
    filename: str

    @property
    def label(self) -> str:
        return f"第 {self.section} 节第 {self.number} 条（{self.title}）"

    @property
    def url(self) -> str:
        return f"{REPO_URL}/blob/main/book/{quote(self.filename)}"


def load_entries(directory: Path) -> list[Entry]:
    result = []
    for path in sorted(directory.glob("*.md")):
        prefix = re.match(r"(\d+)-", path.name)
        if not prefix:
            continue
        text = path.read_text(encoding="utf-8")
        headings = list(re.finditer(r"^### (\d+)\. (.+)$", text, re.M))
        for i, match in enumerate(headings):
            end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
            content = text[match.start():end].strip()
            # 不把截断的片段当成完整知识；缺少任一字段时跳过。
            required = ("- 成本：", "- 收益：", "- 证据等级：", "- 来源：", "- 备注：")
            if not all(field in content for field in required):
                continue
            result.append(Entry(int(prefix[1]), int(match[1]), match[2], content, path.name))
    return result


class KnowledgeIndex:
    def __init__(self, entries: list[Entry]):
        self.entries = entries
        self.counts = [Counter(tokens(e.title + " " + e.title + " " + e.content)) for e in entries]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.average = sum(self.lengths) / max(len(entries), 1)
        self.df = Counter(term for count in self.counts for term in count)

    def search(self, query: str, limit: int = 5) -> list[Entry]:
        if re.search(r"安排时间|时间安排|时间管理", query):
            query += " 打算做 估工期 子任务 退出条件 通知"
        terms = set(tokens(query))
        scored = []
        n = len(self.entries)
        for entry, counts, length in zip(self.entries, self.counts, self.lengths):
            score = 0.0
            for term in terms:
                frequency = counts[term]
                if not frequency:
                    continue
                # 排除几乎每条都有的“时间、成本、收益”等，避免无关匹配。
                df = self.df[term]
                if n > 3 and df / n > 0.75:
                    continue
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                norm = frequency + 1.5 * (0.25 + 0.75 * length / max(self.average, 1))
                score += idf * frequency * 2.5 / norm
                if term in entry.title:
                    score += idf * 1.5
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [entry for _, entry in scored[:limit]]
