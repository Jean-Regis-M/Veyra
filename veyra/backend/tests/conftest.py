"""Compatibility test client for the current Starlette/httpx stack."""

import asyncio

import fastapi.testclient
import httpx


class SynchronousASGITestClient:
    """Synchronous facade over httpx's supported ASGI transport."""

    def __init__(self, app, **_kwargs):
        self._app = app

    def _request(self, method, path, **kwargs):
        async def run():
            transport = httpx.ASGITransport(app=self._app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                return await client.request(method, path, **kwargs)

        return asyncio.run(run())

    def get(self, path, **kwargs):
        return self._request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self._request("POST", path, **kwargs)


# Existing interface tests import this symbol from fastapi.testclient.
fastapi.testclient.TestClient = SynchronousASGITestClient
