from __future__ import annotations

import logging

import structlog
import uvicorn


def main() -> None:
    """Application entry point — configure logging and start ASGI server."""
    from pac.config import load_config

    settings = load_config()

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            (
                structlog.dev.ConsoleRenderer()
                if settings.app.dev_mode
                else structlog.processors.JSONRenderer()
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.app.log_level, logging.INFO),
        ),
    )
    uvicorn.run(
        "pac.app:app",
        host="0.0.0.0",
        port=settings.app.port,
    )


if __name__ == "__main__":
    main()
