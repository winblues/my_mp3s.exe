"""
main.py — runs the proxy (6969) and web UI (6970) in a single process
"""

import asyncio
import uvicorn

from proxy import app as proxy_app
from webui import app as webui_app

PROXY_PORT = 6969
WEBUI_PORT = 6970


async def main():
    proxy_cfg = uvicorn.Config(
        proxy_app, host="0.0.0.0", port=PROXY_PORT, log_level="warning"
    )
    webui_cfg = uvicorn.Config(
        webui_app, host="0.0.0.0", port=WEBUI_PORT, log_level="info"
    )
    await asyncio.gather(
        uvicorn.Server(proxy_cfg).serve(),
        uvicorn.Server(webui_cfg).serve(),
    )


if __name__ == "__main__":
    asyncio.run(main())
