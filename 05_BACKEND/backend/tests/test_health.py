import asyncio
import json
import unittest

from app.main import app


class HealthEndpointTests(unittest.TestCase):
    def test_health_endpoint_returns_ok(self) -> None:
        messages = asyncio.run(self._get_health_response())

        self.assertEqual(messages[0]["status"], 200)
        self.assertEqual(json.loads(messages[1]["body"]), {"status": "ok"})

    async def _get_health_response(self) -> list[dict]:
        messages: list[dict] = []

        async def receive() -> dict:
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: dict) -> None:
            messages.append(message)

        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": "/health",
                "raw_path": b"/health",
                "query_string": b"",
                "headers": [],
                "client": ("testclient", 50000),
                "server": ("testserver", 80),
            },
            receive,
            send,
        )

        return messages
