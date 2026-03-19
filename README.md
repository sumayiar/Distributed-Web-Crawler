# Distributed Async Web Crawler + RAG

This project adds a Python crawler that can process 50k+ pages by splitting work across many async workers and one coordinator service, then query the crawled corpus with a lightweight RAG layer.

## Architecture

- `crawler/coordinator.py`: central lease manager and result API backed by SQLite WAL.
- `crawler/worker.py`: async fetch workers using `aiohttp` with per-domain throttling.
- `crawler/storage.py`: persistent frontier, deduplication, leases, page text, retrieval, and stats.
- `crawler/rag.py`: chunk retrieval and grounded answer synthesis over stored page text.
- `tests/test_crawler.py`: local integration coverage against a fixture site.

The coordinator owns the crawl frontier and hands out URL batches to any number of workers. Workers fetch pages concurrently, extract links, and send discovered URLs back for deduplicated insertion. This lets you scale horizontally by running workers on multiple machines against one coordinator endpoint.

## Run It

Start the coordinator:

```bash
python3 -m crawler.coordinator --db-path crawler.db --port 8080 --max-depth 3
```

Seed a crawl:

```bash
curl -X POST http://127.0.0.1:8080/seed \
  -H 'Content-Type: application/json' \
  -d '{"urls":["https://example.com"]}'
```

Start one worker:

```bash
python3 -m crawler.worker \
  --coordinator-url http://127.0.0.1:8080 \
  --batch-size 200 \
  --concurrency 100 \
  --allowed-domain example.com
```

Start more workers on the same host or different hosts pointing at the same coordinator to scale out. With a few workers at `50-100` concurrent requests each, the crawler is sized for tens of thousands of pages while keeping coordination simple.

Check progress:

```bash
curl http://127.0.0.1:8080/stats
curl http://127.0.0.1:8080/pages?limit=10
```

Query the corpus with RAG after pages are crawled:

```bash
crawler-rag "What does the site say about pricing?"
```

Search raw chunks instead of returning an answer:

```bash
crawler-rag --mode search --limit 3 "pricing tiers"
```

The coordinator also exposes HTTP endpoints for retrieval:

```bash
curl "http://127.0.0.1:8080/search?q=pricing%20tiers&limit=3"
curl -X POST http://127.0.0.1:8080/answer \
  -H 'Content-Type: application/json' \
  -d '{"query":"What does the site say about pricing?","limit":3}'
```

## Notes

- SQLite in WAL mode handles a single coordinator process well. For much larger multi-region deployments, swap `CrawlStore` for Postgres or Redis.
- `allowed-domain` can be repeated to keep the crawl inside a known set of hosts.
- `max-depth`, `batch-size`, and `concurrency` are the main tuning knobs for a 50k+ page run.
- The built-in RAG system is lexical and dependency-light: it stores extracted page text, chunks it at query time, ranks chunks by term overlap plus IDF-like weighting, and builds answers only from retrieved text.
