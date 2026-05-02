from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any


logger = logging.getLogger("eventflow.observability")


def emit_event(event_name: str, **payload: Any) -> None:
    body = {
        "event": event_name,
        "ts_utc": datetime.now(UTC).isoformat(),
        **payload,
    }
    logger.info(json.dumps(body, default=str, ensure_ascii=True))
