import sqlite3
import threading
import time
from math import log
from typing import Dict, Iterable, List
from urllib.parse import urlparse


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS frontier (
    url TEXT PRIMARY KEY,
    depth INTEGER NOT NULL,
    domain TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    discovered_at REAL NOT NULL,
    leased_until REAL,
    worker_id TEXT,
    parent_url TEXT,
    last_error TEXT
);
CREATE INDEX IF NOT EXISTS idx_frontier_status ON frontier(status, leased_until, discovered_at);
CREATE INDEX IF NOT EXISTS idx_frontier_domain ON frontier(domain, status);

CREATE TABLE IF NOT EXISTS pages (
    url TEXT PRIMARY KEY,
    status_code INTEGER,
    content_type TEXT,
    fetched_at REAL NOT NULL,
    title TEXT,
    body_text TEXT NOT NULL DEFAULT '',
    html_bytes INTEGER NOT NULL,
    out_links INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS crawl_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    worker_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    created_at REAL NOT NULL,
    detail TEXT
);
"""


class CrawlStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.db_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(pages)").fetchall()
            }
            if "body_text" not in columns:
                connection.execute(
                    "ALTER TABLE pages ADD COLUMN body_text TEXT NOT NULL DEFAULT ''"
                )

    def seed(self, urls: Iterable[str], depth: int = 0):
        now = time.time()
        rows = []
        for url in urls:
            rows.append((url, depth, urlparse(url).netloc, now))
        with self._lock, self._connect() as connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO frontier (url, depth, domain, discovered_at)
                VALUES (?, ?, ?, ?)
                """,
                rows,
            )

    def reclaim_expired_leases(self):
        now = time.time()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE frontier
                SET status = 'pending', leased_until = NULL, worker_id = NULL
                WHERE status = 'leased' AND leased_until < ?
                """,
                (now,),
            )

    def lease_batch(self, worker_id: str, batch_size: int, lease_seconds: int, max_depth: int):
        now = time.time()
        leased_until = now + lease_seconds
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT url, depth
                FROM frontier
                WHERE status = 'pending' AND depth <= ?
                ORDER BY depth ASC, discovered_at ASC
                LIMIT ?
                """,
                (max_depth, batch_size),
            ).fetchall()
            for row in rows:
                connection.execute(
                    """
                    UPDATE frontier
                    SET status = 'leased', leased_until = ?, worker_id = ?
                    WHERE url = ?
                    """,
                    (leased_until, worker_id, row["url"]),
                )
            connection.commit()
        return [{"url": row["url"], "depth": row["depth"]} for row in rows]

    def complete(
        self,
        worker_id: str,
        url: str,
        depth: int,
        status_code: int,
        content_type: str,
        html_bytes: int,
        title: str,
        body_text: str,
        discovered_urls: Iterable[str],
        max_depth: int,
    ):
        now = time.time()
        normalized = []
        next_depth = depth + 1
        if next_depth <= max_depth:
            for child_url in discovered_urls:
                normalized.append(
                    (child_url, next_depth, urlparse(child_url).netloc, now, url)
                )
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE frontier
                SET status = 'done', leased_until = NULL, worker_id = NULL, last_error = NULL
                WHERE url = ? AND worker_id = ?
                """,
                (url, worker_id),
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO pages
                (url, status_code, content_type, fetched_at, title, body_text, html_bytes, out_links)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    url,
                    status_code,
                    content_type,
                    now,
                    title,
                    body_text,
                    html_bytes,
                    len(normalized),
                ),
            )
            if normalized:
                connection.executemany(
                    """
                    INSERT OR IGNORE INTO frontier
                    (url, depth, domain, discovered_at, parent_url)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    normalized,
                )
            connection.execute(
                """
                INSERT INTO crawl_events (url, worker_id, event_type, created_at, detail)
                VALUES (?, ?, 'completed', ?, ?)
                """,
                (url, worker_id, now, str(status_code)),
            )

    def fail(self, worker_id: str, url: str, message: str):
        now = time.time()
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                UPDATE frontier
                SET status = 'failed', leased_until = NULL, worker_id = NULL, last_error = ?
                WHERE url = ? AND worker_id = ?
                """,
                (message[:500], url, worker_id),
            )
            connection.execute(
                """
                INSERT INTO crawl_events (url, worker_id, event_type, created_at, detail)
                VALUES (?, ?, 'failed', ?, ?)
                """,
                (url, worker_id, now, message[:500]),
            )

    def stats(self) -> Dict[str, int]:
        with self._connect() as connection:
            totals = connection.execute(
                """
                SELECT
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending,
                    SUM(CASE WHEN status = 'leased' THEN 1 ELSE 0 END) AS leased,
                    SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                    COUNT(*) AS frontier_total
                FROM frontier
                """
            ).fetchone()
            page_count = connection.execute(
                "SELECT COUNT(*) AS page_count FROM pages"
            ).fetchone()
        return {
            "pending": totals["pending"] or 0,
            "leased": totals["leased"] or 0,
            "done": totals["done"] or 0,
            "failed": totals["failed"] or 0,
            "frontier_total": totals["frontier_total"] or 0,
            "page_count": page_count["page_count"] or 0,
        }

    def top_pages(self, limit: int = 20) -> List[Dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT url, status_code, title, body_text, html_bytes, out_links, fetched_at
                FROM pages
                ORDER BY fetched_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def iter_page_documents(self):
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT url, title, body_text
                FROM pages
                WHERE COALESCE(body_text, '') != ''
                ORDER BY fetched_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def search_documents(self, query: str, limit: int = 5, chunk_size: int = 600):
        terms = _tokenize(query)
        if not terms:
            return []

        documents = self.iter_page_documents()
        chunks = []
        doc_freq = {}
        for doc in documents:
            for index, chunk in enumerate(_chunk_text(doc["body_text"], chunk_size)):
                tokens = set(_tokenize(chunk))
                if not tokens:
                    continue
                chunk_record = {
                    "url": doc["url"],
                    "title": doc["title"] or doc["url"],
                    "chunk_id": index,
                    "text": chunk,
                    "tokens": tokens,
                }
                chunks.append(chunk_record)
                for token in tokens:
                    doc_freq[token] = doc_freq.get(token, 0) + 1

        if not chunks:
            return []

        total_chunks = len(chunks)
        scored = []
        query_terms = set(terms)
        for chunk in chunks:
            overlap = chunk["tokens"] & query_terms
            if not overlap:
                continue
            score = 0.0
            for token in overlap:
                score += log((1 + total_chunks) / (1 + doc_freq[token])) + 1.0
            score += len(overlap) / max(len(query_terms), 1)
            scored.append(
                {
                    "url": chunk["url"],
                    "title": chunk["title"],
                    "chunk_id": chunk["chunk_id"],
                    "score": round(score, 4),
                    "text": chunk["text"],
                }
            )

        scored.sort(key=lambda item: (-item["score"], item["url"], item["chunk_id"]))
        return scored[:limit]


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


def _chunk_text(text: str, chunk_size: int):
    normalized = " ".join(text.split())
    if not normalized:
        return []
    words = normalized.split(" ")
    chunks = []
    current = []
    current_len = 0
    for word in words:
        extra = len(word) + (1 if current else 0)
        if current and current_len + extra > chunk_size:
            chunks.append(" ".join(current))
            current = [word]
            current_len = len(word)
            continue
        current.append(word)
        current_len += extra
    if current:
        chunks.append(" ".join(current))
    return chunks
