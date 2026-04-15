import asyncio
import json
import uuid
from dataclasses import dataclass
from typing import Any


class ProtocolClientError(Exception):
    pass


@dataclass
class LocalProtocolClient:
    host: str = "127.0.0.1"
    port: int = 8787
    version: str = "v0"
    source: str = "orchestrator"
    target: str = "alsp_adapter"

    async def request(
        self,
        action: str,
        payload: dict[str, Any],
        trace_id: str,
        timeout_ms: int = 30_000,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        envelope = {
            "version": self.version,
            "request_id": request_id,
            "trace_id": trace_id,
            "session_id": session_id,
            "source": self.source,
            "target": self.target,
            "action": action,
            "payload": payload,
            "meta": {"timeout_ms": timeout_ms},
        }
        line = json.dumps(envelope, ensure_ascii=False) + "\n"

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=timeout_ms / 1000.0,
            )
        except TimeoutError as exc:
            raise ProtocolClientError("connection timeout") from exc
        except OSError as exc:
            raise ProtocolClientError(f"connection failed: {exc}") from exc

        try:
            writer.write(line.encode("utf-8"))
            await writer.drain()
            raw = await asyncio.wait_for(reader.readline(), timeout=timeout_ms / 1000.0)
            if not raw:
                raise ProtocolClientError("empty response from adapter")
            resp = json.loads(raw.decode("utf-8"))
        except TimeoutError as exc:
            raise ProtocolClientError("request timeout") from exc
        except json.JSONDecodeError as exc:
            raise ProtocolClientError(f"invalid response json: {exc}") from exc
        finally:
            writer.close()
            await writer.wait_closed()

        if resp.get("request_id") != request_id:
            raise ProtocolClientError("request_id mismatch in response")
        if resp.get("trace_id") != trace_id:
            raise ProtocolClientError("trace_id mismatch in response")
        return resp
