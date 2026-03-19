from typing import List, Optional

from crawler.storage import CrawlStore


class RagEngine:
    def __init__(self, store: CrawlStore, default_limit: int = 5):
        self.store = store
        self.default_limit = default_limit

    def search(self, query: str, limit: Optional[int] = None):
        return self.store.search_documents(query=query, limit=limit or self.default_limit)

    def answer(self, query: str, limit: Optional[int] = None):
        results = self.search(query=query, limit=limit)
        if not results:
            return {
                "query": query,
                "answer": "I could not find relevant context in the crawled corpus.",
                "results": [],
            }

        answer_parts = []
        seen = set()
        for result in results:
            for snippet in _best_sentences(result["text"], query, max_sentences=2):
                normalized = snippet.strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                answer_parts.append(normalized)
                if len(answer_parts) == 3:
                    break
            if len(answer_parts) == 3:
                break

        return {
            "query": query,
            "answer": " ".join(answer_parts) or results[0]["text"],
            "results": results,
        }


def _best_sentences(text: str, query: str, max_sentences: int):
    query_tokens = set(_tokenize(query))
    sentences = _split_sentences(text)
    if not sentences:
        return [text.strip()]

    ranked = sorted(
        sentences,
        key=lambda sentence: (
            -len(query_tokens & set(_tokenize(sentence))),
            abs(len(sentence) - 120),
        ),
    )
    return ranked[:max_sentences]


def _split_sentences(text: str):
    sentences: List[str] = []
    current: List[str] = []
    for char in text:
        current.append(char)
        if char in ".!?":
            sentence = "".join(current).strip()
            if sentence:
                sentences.append(sentence)
            current = []
    tail = "".join(current).strip()
    if tail:
        sentences.append(tail)
    return sentences


def _tokenize(text: str):
    token = []
    tokens = []
    for char in text.lower():
        if char.isalnum():
            token.append(char)
            continue
        if token:
            tokens.append("".join(token))
            token = []
    if token:
        tokens.append("".join(token))
    return tokens
