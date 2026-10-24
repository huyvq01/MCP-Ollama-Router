"""JSON events on stderr; stdout is reserved for the MCP stdio protocol."""
import json
import logging
import sys
from datetime import datetime, timezone

from app.runtime import runtime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            'time': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'event': record.getMessage(),
        }, ensure_ascii=True)


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(runtime.log_level)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)


logger = logging.getLogger('app')
