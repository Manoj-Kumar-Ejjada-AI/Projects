import hashlib
import json

from datetime import datetime, timezone
from pathlib import Path


class AuditLogger:

    def __init__(
                self,
                path: str,
                ):

        self.path = Path(path)

        self.path.parent.mkdir(
                            parents=True,
                            exist_ok=True,
                            )

    def record(
                self,
                *,
                trace_id,
                tenant,
                caller,
                delegator,
                tool,
                arguments,
                duration_ms,
                status,
                error_code=None,
            ):

        payload = json.dumps(
            arguments,
            sort_keys=True,
            default=str,
        ).encode()

        args_hash = (
            "sha256:"
            + hashlib.sha256(
                payload
            ).hexdigest()
        )

        event = {
            "ts": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
            "trace_id": trace_id,
            "tenant": tenant,
            "caller": caller,
            "delegator": delegator,
            "tool": tool,
            "args_hash": args_hash,
            "duration_ms": round(
                duration_ms,
                3,
            ),
            "status": status,
            "error_code": error_code,
        }

        with self.path.open(
            "a",
            encoding="utf-8",
        ) as fh:

            fh.write(
                json.dumps(event)
                + "\n"
            )