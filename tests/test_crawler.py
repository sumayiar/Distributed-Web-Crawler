import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import aiohttp
from aiohttp import web

from crawler.coordinator import build_app
from crawler.rag import RagEngine
from crawler.storage import CrawlStore


class FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        pages = {
            "/": '<html><head><title>Home</title></head><body><a href="/a">A</a><a href="/b">B</a></body></html>',
            "/a": '<html><head><title>Page A</title></head><body><a href="/b">B</a></body></html>',
            "/b": '<html><head><title>Page B</title></head><body><a href="/c">C</a></body></html>',
            "/c": '<html><head><title>Page C</title></head><body>leaf</body></html>',
        }
        body = pages.get(self.path, "missing")
        status = 200 if self.path in pages else 404
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format, *args):
        return


class CrawlerIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tempdir.name) / "crawler.db")

        self.fixture_server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        self.fixture_port = self.fixture_server.server_address[1]
        self.fixture_thread = threading.Thread(
            target=self.fixture_server.serve_forever, daemon=True
        )
        self.fixture_thread.start()

        self.app = build_app(self.db_path, lease_seconds=5, max_depth=3)
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await self.site.start()
        sockets = list(self.site._server.sockets)
        self.coordinator_port = sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        await self.runner.cleanup()
        self.fixture_server.shutdown()
        self.fixture_server.server_close()
        self.tempdir.cleanup()

    async def post_json(self, path, payload):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"http://127.0.0.1:{self.coordinator_port}{path}",
                json=payload,
            ) as response:
                response.raise_for_status()
                return await response.json()

    async def get_json(self, path):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://127.0.0.1:{self.coordinator_port}{path}"
            ) as response:
                response.raise_for_status()
                return await response.json()

    async def test_coordinator_tracks_discovered_pages(self):
        root_url = f"http://127.0.0.1:{self.fixture_port}/"
        await self.post_json("/seed", {"urls": [root_url]})

        batch = await self.post_json("/lease", {"worker_id": "worker-1", "batch_size": 5})
        self.assertEqual(len(batch["tasks"]), 1)
        first_task = batch["tasks"][0]
        await self.post_json(
            "/complete",
            {
                "worker_id": "worker-1",
                "url": first_task["url"],
                "depth": first_task["depth"],
                "status_code": 200,
                "content_type": "text/html",
                "html_bytes": 120,
                "title": "Home",
                "discovered_urls": [
                    f"http://127.0.0.1:{self.fixture_port}/a",
                    f"http://127.0.0.1:{self.fixture_port}/b",
                ],
            },
        )

        batch = await self.post_json("/lease", {"worker_id": "worker-2", "batch_size": 10})
        self.assertEqual(len(batch["tasks"]), 2)

        stats = await self.get_json("/stats")
        self.assertEqual(stats["done"], 1)
        self.assertEqual(stats["leased"], 2)
        self.assertEqual(stats["frontier_total"], 3)

    async def test_worker_can_crawl_fixture_site(self):
        from crawler.worker import Worker

        root_url = f"http://127.0.0.1:{self.fixture_port}/"
        await self.post_json("/seed", {"urls": [root_url]})
        worker = Worker(
            coordinator_url=f"http://127.0.0.1:{self.coordinator_port}",
            worker_id="fixture-worker",
            batch_size=2,
            concurrency=2,
            max_depth=3,
            request_timeout=5,
            allowed_domains=[f"127.0.0.1:{self.fixture_port}"],
        )

        async with aiohttp.ClientSession() as session:
            for _ in range(4):
                leased = await worker.lease_tasks(session)
                if not leased:
                    break
                await worker.process_task(leased[0], session)
                if len(leased) > 1:
                    await worker.process_task(leased[1], session)
                await asyncio_sleep()

        stats = await self.get_json("/stats")
        self.assertGreaterEqual(stats["done"], 4)
        self.assertEqual(stats["failed"], 0)
        self.assertEqual(stats["pending"], 0)

    async def test_worker_stores_page_text_for_retrieval(self):
        from crawler.worker import Worker

        root_url = f"http://127.0.0.1:{self.fixture_port}/"
        await self.post_json("/seed", {"urls": [root_url]})
        worker = Worker(
            coordinator_url=f"http://127.0.0.1:{self.coordinator_port}",
            worker_id="text-worker",
            batch_size=1,
            concurrency=1,
            max_depth=1,
            request_timeout=5,
            allowed_domains=[f"127.0.0.1:{self.fixture_port}"],
        )

        async with aiohttp.ClientSession() as session:
            leased = await worker.lease_tasks(session)
            self.assertEqual(len(leased), 1)
            await worker.process_task(leased[0], session)

        store = CrawlStore(self.db_path)
        pages = store.top_pages(limit=1)
        self.assertIn("Home", pages[0]["body_text"])

    async def test_rag_engine_returns_relevant_context_and_answer(self):
        store = CrawlStore(self.db_path)
        store.seed([f"http://127.0.0.1:{self.fixture_port}/"], depth=0)
        store.complete(
            worker_id="seed-worker",
            url=f"http://127.0.0.1:{self.fixture_port}/guide",
            depth=0,
            status_code=200,
            content_type="text/html",
            html_bytes=180,
            title="Guide",
            body_text=(
                "Python retrieval augmented generation uses document chunks. "
                "Chunking improves recall. Grounded answers cite retrieved context."
            ),
            discovered_urls=[],
            max_depth=3,
        )
        store.complete(
            worker_id="seed-worker",
            url=f"http://127.0.0.1:{self.fixture_port}/map",
            depth=0,
            status_code=200,
            content_type="text/html",
            html_bytes=90,
            title="Map",
            body_text="Cartography and terrain rendering are unrelated topics.",
            discovered_urls=[],
            max_depth=3,
        )

        engine = RagEngine(store)
        results = engine.search("How does chunking help retrieval?")
        self.assertTrue(results)
        self.assertEqual(results[0]["title"], "Guide")
        self.assertIn("Chunking improves recall", results[0]["text"])

        answer = engine.answer("Why does chunking help retrieval?")
        self.assertIn("Chunking improves recall", answer["answer"])
        self.assertEqual(answer["results"][0]["title"], "Guide")


async def asyncio_sleep():
    import asyncio

    await asyncio.sleep(0.05)


if __name__ == "__main__":
    unittest.main()
