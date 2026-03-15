import argparse
import asyncio
import socket
import time
from typing import Dict, List
from urllib.parse import urlparse

import aiohttp

from crawler.html import extract_links


def extract_title(html: str):
    lower = html.lower()
    start = lower.find("<title>")
    end = lower.find("</title>")
    if start == -1 or end == -1 or end <= start:
        return ""
    return html[start + 7 : end].strip()


class Worker:
    def __init__(
        self,
        coordinator_url: str,
        worker_id: str,
        batch_size: int,
        concurrency: int,
        max_depth: int,
        request_timeout: int,
        allowed_domains: List[str],
    ):
        self.coordinator_url = coordinator_url.rstrip("/")
        self.worker_id = worker_id
        self.batch_size = batch_size
        self.concurrency = concurrency
        self.max_depth = max_depth
        self.request_timeout = request_timeout
        self.allowed_domains = set(allowed_domains)
        self.domain_limits: Dict[str, asyncio.Semaphore] = {}

    def _domain_semaphore(self, url: str):
        domain = urlparse(url).netloc
        if domain not in self.domain_limits:
            self.domain_limits[domain] = asyncio.Semaphore(2)
        return self.domain_limits[domain]

    def _should_keep(self, url: str):
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False
        if not self.allowed_domains:
            return True
        return parsed.netloc in self.allowed_domains

    async def lease_tasks(self, session: aiohttp.ClientSession):
        async with session.post(
            f"{self.coordinator_url}/lease",
            json={"worker_id": self.worker_id, "batch_size": self.batch_size},
        ) as response:
            response.raise_for_status()
            payload = await response.json()
            return payload["tasks"]

    async def report_complete(self, session: aiohttp.ClientSession, payload: Dict[str, object]):
        async with session.post(f"{self.coordinator_url}/complete", json=payload) as response:
            response.raise_for_status()

    async def report_failure(self, session: aiohttp.ClientSession, payload: Dict[str, object]):
        async with session.post(f"{self.coordinator_url}/fail", json=payload) as response:
            response.raise_for_status()

    async def fetch_and_parse(self, url: str, session: aiohttp.ClientSession):
        timeout = aiohttp.ClientTimeout(total=self.request_timeout)
        semaphore = self._domain_semaphore(url)
        async with semaphore:
            async with session.get(url, timeout=timeout, allow_redirects=True) as response:
                content_type = response.headers.get("Content-Type", "")
                body = await response.text(errors="ignore")
                title = extract_title(body)
                links = []
                if "text/html" in content_type:
                    links = [link for link in extract_links(str(response.url), body) if self._should_keep(link)]
                return {
                    "status_code": response.status,
                    "content_type": content_type,
                    "html_bytes": len(body.encode("utf-8")),
                    "title": title,
                    "discovered_urls": links,
                }

    async def process_task(self, task: Dict[str, object], session: aiohttp.ClientSession):
        url = task["url"]
        depth = int(task["depth"])
        try:
            result = await self.fetch_and_parse(url, session)
            result.update(
                {
                    "worker_id": self.worker_id,
                    "url": url,
                    "depth": depth,
                }
            )
            await self.report_complete(session, result)
        except Exception as exc:
            await self.report_failure(
                session,
                {
                    "worker_id": self.worker_id,
                    "url": url,
                    "error": str(exc),
                },
            )

    async def run(self):
        connector = aiohttp.TCPConnector(limit=max(self.concurrency * 2, 20), ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            while True:
                tasks = await self.lease_tasks(session)
                if not tasks:
                    await asyncio.sleep(1.0)
                    continue
                for index in range(0, len(tasks), self.concurrency):
                    chunk = tasks[index : index + self.concurrency]
                    await asyncio.gather(
                        *(self.process_task(task, session) for task in chunk)
                    )


def parse_args():
    parser = argparse.ArgumentParser(description="Run an async crawl worker.")
    parser.add_argument("--coordinator-url", default="http://127.0.0.1:8080")
    parser.add_argument("--worker-id", default=f"{socket.gethostname()}-{int(time.time())}")
    parser.add_argument("--batch-size", default=100, type=int)
    parser.add_argument("--concurrency", default=50, type=int)
    parser.add_argument("--max-depth", default=3, type=int)
    parser.add_argument("--request-timeout", default=15, type=int)
    parser.add_argument("--allowed-domain", action="append", default=[])
    return parser.parse_args()


async def amain():
    args = parse_args()
    worker = Worker(
        coordinator_url=args.coordinator_url,
        worker_id=args.worker_id,
        batch_size=args.batch_size,
        concurrency=args.concurrency,
        max_depth=args.max_depth,
        request_timeout=args.request_timeout,
        allowed_domains=args.allowed_domain,
    )
    await worker.run()


def main():
    asyncio.run(amain())


if __name__ == "__main__":
    main()
