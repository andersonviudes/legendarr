import time

from legendarr_backend.bootstrap import build_scheduler
from legendarr_backend.shared_kernel.logging.setup import configure_logging


def main() -> None:
    configure_logging()
    scheduler = build_scheduler()
    scheduler.start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        scheduler.shutdown()


if __name__ == "__main__":
    main()
