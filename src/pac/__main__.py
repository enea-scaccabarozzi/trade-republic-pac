from __future__ import annotations

import structlog

logger = structlog.get_logger()


def main() -> None:
    """Application entry point."""
    logger.info("pac_starting")


if __name__ == "__main__":
    main()
