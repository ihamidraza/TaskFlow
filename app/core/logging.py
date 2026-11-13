"""Structured (JSON) logging using only the standard library.

One JSON object per line is easy for log tools (Datadog, Loki, CloudWatch)
to search and filter, e.g. `status >= 500` or `duration_ms > 200`.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

# Attributes every LogRecord has. Anything else was passed via `extra={...}`
# and becomes a field in the JSON output.
_STANDARD_ATTRS = set(vars(logging.makeLogRecord({}))) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update({k: v for k, v in vars(record).items() if k not in _STANDARD_ATTRS})
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]  # replace, so calling this twice doesn't duplicate lines
    root.setLevel(level)

    # Our middleware logs every request, so silence uvicorn's own access log.
    logging.getLogger("uvicorn.access").disabled = True
