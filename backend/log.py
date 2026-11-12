"""Structured logging: every line has a fixed prefix and then the event's fields as key=value.

    2026-11-12 19:55:01 INFO analysis: image analyzed event_id=a3f09c1e7b2d4410 camera_id=1 status=done processing_ms=153 detections=7

Fields make the log easy to filter, e.g. every line of one door event:
    docker compose logs web | grep event_id=a3f09c1e7b2d4410
"""
import logging
import sys

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _format_value(value) -> str:
    if isinstance(value, (list, tuple, set)):
        value = ",".join(str(item) for item in (sorted(value) if isinstance(value, set) else value))
    value = str(value)
    # Quoted when it has spaces, so every field stays one key=value token
    return f'"{value}"' if " " in value or not value else value


class FieldsFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        fields = getattr(record, "fields", None)
        if fields:
            line += " " + " ".join(f"{key}={_format_value(value)}" for key, value in fields.items())
        return line


def configure_logging(level: int = logging.INFO) -> None:
    """Send the app's logs (analysis, inventory, vision, main) to stdout, where docker compose logs reads them."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(FieldsFormatter(FORMAT, DATE_FORMAT))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # SQLAlchemy's engine logs every query through echo=True already; don't print them twice
    logging.getLogger("sqlalchemy").propagate = False


def log(logger: logging.Logger, message: str, level: int = logging.INFO, **fields) -> None:
    """Log a message with structured fields: log(logger, "image analyzed", camera_id=1, detections=7)."""
    logger.log(level, message, extra={"fields": fields})
