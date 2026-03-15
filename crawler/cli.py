from crawler.coordinator import main as coordinator_main
from crawler.worker import main as worker_main


def run_coordinator():
    coordinator_main()


def run_worker():
    worker_main()
