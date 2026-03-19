import argparse
import json

from crawler.coordinator import main as coordinator_main
from crawler.rag import RagEngine
from crawler.storage import CrawlStore
from crawler.worker import main as worker_main


def run_coordinator():
    coordinator_main()


def run_worker():
    worker_main()


def run_rag_query():
    parser = argparse.ArgumentParser(description="Query the crawled corpus with lexical RAG.")
    parser.add_argument("query", help="Question or search query")
    parser.add_argument("--db-path", default="crawler.db")
    parser.add_argument("--limit", default=5, type=int)
    parser.add_argument(
        "--mode",
        choices=["answer", "search"],
        default="answer",
        help="Return a synthesized grounded answer or the raw retrieval results.",
    )
    args = parser.parse_args()

    engine = RagEngine(CrawlStore(args.db_path), default_limit=args.limit)
    payload = (
        engine.answer(args.query, limit=args.limit)
        if args.mode == "answer"
        else {"query": args.query, "results": engine.search(args.query, limit=args.limit)}
    )
    print(json.dumps(payload, indent=2))
