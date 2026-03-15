import argparse
from aiohttp import web

from crawler.storage import CrawlStore


class Coordinator:
    def __init__(self, store: CrawlStore, lease_seconds: int, max_depth: int):
        self.store = store
        self.lease_seconds = lease_seconds
        self.max_depth = max_depth

    async def handle_seed(self, request: web.Request):
        payload = await request.json()
        urls = payload.get("urls") or []
        if not urls:
            return web.json_response({"error": "urls must not be empty"}, status=400)
        self.store.seed(urls, depth=0)
        return web.json_response({"seeded": len(urls)})

    async def handle_lease(self, request: web.Request):
        self.store.reclaim_expired_leases()
        payload = await request.json()
        worker_id = payload.get("worker_id")
        batch_size = int(payload.get("batch_size", 50))
        if not worker_id:
            return web.json_response({"error": "worker_id is required"}, status=400)
        urls = self.store.lease_batch(worker_id, batch_size, self.lease_seconds, self.max_depth)
        return web.json_response({"tasks": urls})

    async def handle_complete(self, request: web.Request):
        payload = await request.json()
        self.store.complete(
            worker_id=payload["worker_id"],
            url=payload["url"],
            depth=int(payload["depth"]),
            status_code=int(payload["status_code"]),
            content_type=payload.get("content_type") or "",
            html_bytes=int(payload.get("html_bytes") or 0),
            title=payload.get("title") or "",
            discovered_urls=payload.get("discovered_urls") or [],
            max_depth=self.max_depth,
        )
        return web.json_response({"ok": True})

    async def handle_fail(self, request: web.Request):
        payload = await request.json()
        self.store.fail(
            worker_id=payload["worker_id"],
            url=payload["url"],
            message=payload.get("error") or "unknown error",
        )
        return web.json_response({"ok": True})

    async def handle_stats(self, request: web.Request):
        return web.json_response(self.store.stats())

    async def handle_pages(self, request: web.Request):
        limit = int(request.query.get("limit", "20"))
        return web.json_response({"pages": self.store.top_pages(limit=limit)})


def build_app(db_path: str, lease_seconds: int, max_depth: int):
    store = CrawlStore(db_path)
    coordinator = Coordinator(store, lease_seconds=lease_seconds, max_depth=max_depth)
    app = web.Application()
    app.add_routes(
        [
            web.post("/seed", coordinator.handle_seed),
            web.post("/lease", coordinator.handle_lease),
            web.post("/complete", coordinator.handle_complete),
            web.post("/fail", coordinator.handle_fail),
            web.get("/stats", coordinator.handle_stats),
            web.get("/pages", coordinator.handle_pages),
        ]
    )
    return app


def parse_args():
    parser = argparse.ArgumentParser(description="Run the crawl coordinator service.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8080, type=int)
    parser.add_argument("--db-path", default="crawler.db")
    parser.add_argument("--lease-seconds", default=60, type=int)
    parser.add_argument("--max-depth", default=3, type=int)
    return parser.parse_args()


def main():
    args = parse_args()
    web.run_app(
        build_app(args.db_path, args.lease_seconds, args.max_depth),
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
